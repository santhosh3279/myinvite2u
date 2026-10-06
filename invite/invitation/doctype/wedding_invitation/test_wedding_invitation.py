import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.utils import add_days, today
from frappe.website.page_renderers.document_page import DocumentPage
from frappe.website.utils import clear_cache

from invite.api import submit_rsvp
from invite.domains import InvitationDomainPage, base_domain, domain_from_names, validate_invitation_domain


class TestWeddingInvitation(unittest.TestCase):
	def setUp(self):
		token = patch("frappe.sessions.get_csrf_token", return_value="test-token")
		token.start()
		self.addCleanup(token.stop)
		self.user = frappe.session.user
		frappe.set_user("Administrator")
		frappe.db.savepoint("wedding_test")
		self.invitation = frappe.get_doc({
			"doctype": "Wedding Invitation", "bride_name": "Anna " + uuid4().hex[:8],
			"groom_name": "James", "wedding_date": add_days(today(), 100),
			"wedding_time": "14:30:00", "timezone": "Asia/Kolkata",
			"is_published": 1, "enable_rsvp": 1, "max_guests": 3,
			"rsvp_deadline": add_days(today(), 90),
			"events": [{"event_name": "Ceremony", "venue_name": "Garden Hall",
						"event_datetime": add_days(today(), 100) + " 14:30:00"}],
		}).insert()
		self.routes = [self.invitation.route]

	def tearDown(self):
		frappe.set_user(self.user)
		frappe.db.rollback(save_point="wedding_test")
		for route in self.routes:
			clear_cache(route)

	def rsvp(self, **overrides):
		data = dict(route=self.invitation.route, guest_name="Guest", email="guest@example.com", attendance="Attending", guest_count=2)
		data.update(overrides)
		return submit_rsvp(**data)

	def test_generated_address_and_duplicate(self):
		self.assertEqual(self.invitation.route, f"{self.invitation.bride_name.lower().replace(' ', '-')}&james-{self.invitation.wedding_date}")
		duplicate = frappe.copy_doc(self.invitation)
		with self.assertRaises(frappe.ValidationError):
			duplicate.insert()
		old_route = self.invitation.route
		self.invitation.groom_name = "John"
		self.invitation.save()
		self.routes.append(self.invitation.route)
		self.assertNotEqual(old_route, self.invitation.route)

	def test_public_render_and_escaping(self):
		self.invitation.invitation_message = '<b>Welcome</b>'
		self.invitation.save()
		frappe.set_user("Guest")
		page = DocumentPage(self.invitation.route)
		self.assertTrue(page.can_render())
		html = page.get_html()
		self.assertIn("&lt;b&gt;Welcome&lt;/b&gt;", html)
		self.assertNotIn('<b>Welcome</b>', html)
		self.assertIn('+05:30', html)
		self.assertIn('id="rsvp-form"', html)
		self.assertFalse(frappe.has_permission("Wedding RSVP", "read"))
		self.assertFalse(frappe.has_permission("Wedding Invitation", "read"))

	def test_guest_response_and_decline(self):
		frappe.set_user("Guest")
		self.assertTrue(self.rsvp()["success"])
		self.assertTrue(self.rsvp(attendance="Not Attending", guest_count=0)["success"])
		rows = frappe.get_all("Wedding RSVP", filters={"invitation": self.invitation.name}, fields=["guest_count", "attendance"])
		self.assertEqual(len(rows), 2)
		self.assertEqual(next(row.guest_count for row in rows if row.attendance == "Not Attending"), 0)

	def test_response_validation(self):
		for invalid in ({"guest_count": 4}, {"guest_count": "1.5"}, {"guest_name": ""}, {"email": "invalid"}, {"attendance": "Maybe"}, {"message": "x" * 2001}, {"website": "spam"}):
			with self.subTest(invalid=invalid), self.assertRaises(frappe.ValidationError):
				self.rsvp(**invalid)
		self.assertEqual(frappe.db.count("Wedding RSVP", {"invitation": self.invitation.name}), 0)

	def test_unpublished_disabled_and_expired(self):
		self.invitation.is_published = 0
		self.invitation.save()
		self.assertFalse(DocumentPage(self.invitation.route).can_render())
		with self.assertRaises(frappe.DoesNotExistError):
			self.rsvp()
		self.invitation.is_published = 1
		self.invitation.enable_rsvp = 0
		self.invitation.save()
		with self.assertRaises(frappe.ValidationError):
			self.rsvp()
		self.invitation.enable_rsvp = 1
		self.invitation.rsvp_deadline = add_days(today(), -1)
		self.invitation.save()
		with self.assertRaises(frappe.ValidationError):
			self.rsvp()
		context = frappe._dict()
		self.invitation.get_context(context)
		self.assertFalse(context.rsvp_open)

	def test_settings_validation(self):
		for field, value in (("timezone", "Invalid/Zone"), ("max_guests", 0), ("hero_image", "javascript:alert(1)"), ("music_file", "/private/files/song.mp3"), ("rsvp_deadline", add_days(today(), 101))):
			with self.subTest(field=field):
				doc = frappe.copy_doc(self.invitation)
				doc.bride_name = "Unique " + uuid4().hex[:8]
				doc.set(field, value)
				with self.assertRaises(frappe.ValidationError):
					doc.insert()

	def test_midnight_and_morning_countdown(self):
		for wedding_time in ("00:00:00", "09:30:00"):
			with self.subTest(wedding_time=wedding_time):
				self.invitation.wedding_time = wedding_time
				self.invitation.save()
				self.invitation.reload()
				context = frappe._dict()
				self.invitation.get_context(context)
				self.assertIn(f"T{wedding_time}+05:30", context.wedding_iso)

	def activate_domain(self):
		self.invitation.enable_subdomain = 1
		self.invitation.invitation_domain = "couple-" + uuid4().hex[:8] + "." + base_domain()
		self.invitation.save()
		return self.invitation.invitation_domain

	def test_domain_validation_and_uniqueness(self):
		domain = self.activate_domain()
		self.assertEqual(self.invitation.public_url, f"https://{domain}/")
		self.assertEqual(validate_invitation_domain(domain.upper()), domain)
		for invalid in ("", "example.com", "anna&james." + base_domain(), "https://" + domain, domain + "/", domain + ":8001", "nested." + domain, "-bad." + base_domain(), "www." + base_domain()):
			with self.subTest(invalid=invalid), self.assertRaises(frappe.ValidationError):
				validate_invitation_domain(invalid)
		duplicate = frappe.copy_doc(self.invitation)
		duplicate.bride_name = "Another " + uuid4().hex[:8]
		with self.assertRaises(frappe.ValidationError):
			duplicate.insert()
		self.invitation.enable_subdomain = 0
		self.invitation.save()
		self.assertEqual(self.invitation.public_url, "/" + self.invitation.route)

	def test_domain_renderer_resolves_only_assigned_invitation(self):
		domain = self.activate_domain()
		with patch.object(frappe.local, "request", SimpleNamespace(host=domain + ":8001", path="/"), create=True):
			page = InvitationDomainPage("index")
			self.assertTrue(page.can_render())
			self.assertTrue(page.found)
			self.assertEqual(page.docname, self.invitation.name)
			frappe.local.request.path = "/someone-else"
			page = InvitationDomainPage("someone-else")
			self.assertTrue(page.can_render())
			self.assertFalse(page.found)
			frappe.local.request.host = "unassigned." + base_domain()
			frappe.local.request.path = "/"
			page = InvitationDomainPage("index")
			self.assertTrue(page.can_render())
			self.assertFalse(page.found)
			frappe.local.request.host = base_domain()
			self.assertFalse(InvitationDomainPage("index").can_render())

	def test_disabled_and_unpublished_domains(self):
		domain = self.activate_domain()
		with patch.object(frappe.local, "request", SimpleNamespace(host=domain, path="/"), create=True):
			for field in ("enable_subdomain", "is_published"):
				self.invitation.set(field, 0)
				self.invitation.save()
				page = InvitationDomainPage("index")
				self.assertTrue(page.can_render())
				self.assertFalse(page.found)
				self.invitation.set(field, 1)
				self.invitation.save()

	def test_rsvp_checks_hostname(self):
		domain = self.activate_domain()
		with patch("invite.api.request_hostname", return_value="unassigned." + base_domain()):
			with self.assertRaises(frappe.DoesNotExistError):
				self.rsvp()
		other = frappe.copy_doc(self.invitation)
		other.bride_name = "Other " + uuid4().hex[:8]
		other.enable_subdomain = 0
		other.invitation_domain = None
		other.insert()
		self.routes.append(other.route)
		with patch("invite.api.request_hostname", return_value=domain):
			with self.assertRaises(frappe.DoesNotExistError):
				self.rsvp(route=other.route)
			self.assertTrue(self.rsvp()["success"])

	def test_domain_autofill_follows_name_changes(self):
		self.assertEqual(self.invitation.invitation_domain, domain_from_names(self.invitation.bride_name, "James"))
		self.invitation.enable_subdomain = 1
		self.invitation.groom_name = "John"
		self.invitation.save()
		self.routes.append(self.invitation.route)
		self.assertEqual(self.invitation.invitation_domain, domain_from_names(self.invitation.bride_name, "John"))
		self.assertEqual(self.invitation.public_url, "https://" + self.invitation.invitation_domain + "/")
		self.assertEqual(domain_from_names(" Ánna Marie ", "James O’Neil"), "anna-marie-james-oneil." + base_domain())
		self.assertLessEqual(len(domain_from_names("a" * 100, "b" * 100).split(".")[0]), 63)

	def test_custom_domain_preserved_and_blank_regenerated(self):
		custom = "our-wedding-" + uuid4().hex[:8] + "." + base_domain()
		self.invitation.invitation_domain = custom
		self.invitation.save()
		self.invitation.groom_name = "John"
		self.invitation.save()
		self.routes.append(self.invitation.route)
		self.assertEqual(self.invitation.invitation_domain, custom)
		self.invitation.invitation_domain = ""
		self.invitation.save()
		self.assertEqual(self.invitation.invitation_domain, domain_from_names(self.invitation.bride_name, "John"))

	def test_light_and_dark_template_selection(self):
		self.assertEqual(self.invitation.invitation_template, "Light")
		for template, theme, stylesheet in (
			("Light", "light", None),
			("Dark", "dark", "wedding-dark.css"),
		):
			with self.subTest(template=template):
				self.invitation.invitation_template = template
				self.invitation.save()
				page = DocumentPage(self.invitation.route)
				self.assertTrue(page.can_render())
				html = page.get_html()
				self.assertIn(f'data-theme="{theme}"', html)
				self.assertIn('id="rsvp-form"', html)
				self.assertIn('id="envelope"', html)
				if stylesheet:
					self.assertIn(stylesheet, html)
				else:
					self.assertNotIn("wedding-dark.css", html)
				context = frappe._dict()
				self.invitation.get_context(context)
				self.assertEqual(context.template, page.template_path)

	def test_template_validation_and_legacy_default(self):
		self.invitation.invitation_template = ""
		self.invitation.save()
		self.assertEqual(self.invitation.invitation_template, "Light")
		self.invitation.invitation_template = "../some-template"
		with self.assertRaises(frappe.ValidationError):
			self.invitation.save()
