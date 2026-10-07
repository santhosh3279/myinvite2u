import json
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import frappe
from frappe import _
from frappe.utils import cint, get_time, getdate, get_datetime, validate_email_address
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.utils import cleanup_page_name

from invite.domains import domain_from_names, validate_invitation_domain


INVITATION_TEMPLATES = {
	"Light": "templates/wedding_invitation.html",
	"Dark": "templates/wedding_invitation_dark.html",
	"Hindu Wedding": "templates/wedding_invitation_hindu.html",
}


def validate_public_url(value, label):
	if not value:
		return
	parts = urlsplit(value)
	if not ((parts.scheme == "https" and parts.netloc) or (value.startswith("/") and not value.startswith("//"))):
		frappe.throw(_("{0} must be an HTTPS URL or a public file path.").format(label))
	if value.startswith("/private/") or "\\" in value or any(ord(c) < 32 for c in value):
		frappe.throw(_("{0} must use a public file.").format(label))


class WeddingInvitation(WebsiteGenerator):
	website = frappe._dict(condition_field="is_published", page_title_field="title", template="templates/wedding_invitation.html")

	def onload(self):
		super().onload()
		self.get("__onload").suggested_invitation_domain = domain_from_names(self.bride_name, self.groom_name)

	def validate(self):
		self.invitation_template = self.invitation_template or "Light"
		if self.invitation_template not in INVITATION_TEMPLATES:
			frappe.throw(_("Please select a Light, Dark or Hindu Wedding invitation template."))
		self.bride_name = (self.bride_name or "").strip()
		self.groom_name = (self.groom_name or "").strip()
		bride = cleanup_page_name(self.bride_name).strip("-.")
		groom = cleanup_page_name(self.groom_name).strip("-.")
		if not bride or not groom:
			frappe.throw(_("Please enter both bride and groom names."))
		self.title = f"{self.bride_name} & {self.groom_name}"
		self.route = f"{bride[:55]}&{groom[:55]}-{getdate(self.wedding_date).isoformat()}"
		duplicate = frappe.db.get_value("Wedding Invitation", {"route": self.route, "name": ["!=", self.name or ""]}, "name")
		if duplicate:
			frappe.throw(_("An invitation for these names and date already exists."))
		previous = self.get_doc_before_save()
		previous_suggestion = domain_from_names(previous.bride_name, previous.groom_name) if previous else ""
		if not self.invitation_domain or (previous_suggestion and self.invitation_domain == previous_suggestion):
			self.invitation_domain = domain_from_names(self.bride_name, self.groom_name)
		if self.enable_subdomain or self.invitation_domain:
			self.invitation_domain = validate_invitation_domain(self.invitation_domain)
			duplicate_domain = frappe.db.get_value("Wedding Invitation", {
				"invitation_domain": self.invitation_domain, "name": ["!=", self.name or ""],
			}, "name")
			if duplicate_domain:
				frappe.throw(_("This invitation domain is already assigned to another invitation."))
		self.public_url = f"https://{self.invitation_domain}/" if self.enable_subdomain else "/" + self.route
		try:
			ZoneInfo(self.timezone)
		except (ZoneInfoNotFoundError, ValueError, TypeError):
			frappe.throw(_("Please enter a valid IANA timezone, for example Asia/Kolkata."))
		if not 1 <= cint(self.max_guests) <= 50:
			frappe.throw(_("Maximum guests must be between 1 and 50."))
		if self.rsvp_deadline and getdate(self.rsvp_deadline) > getdate(self.wedding_date):
			frappe.throw(_("RSVP deadline cannot be after the wedding date."))
		if self.contact_email:
			validate_email_address(self.contact_email, throw=True)
		for key in ("hero_image", "couple_image", "music_file"):
			validate_public_url(self.get(key), self.meta.get_label(key))
		for row in self.events:
			validate_public_url(row.maps_url, _("Directions URL"))
		for row in [*self.gallery, *self.story]:
			validate_public_url(row.image, _("Photo"))
		super().validate()

	def get_context(self, context):
		context.template = INVITATION_TEMPLATES.get(self.invitation_template, INVITATION_TEMPLATES["Light"])
		context.no_cache = 1
		context.sitemap = False
		wedding_time = self.wedding_time if self.wedding_time is not None and self.wedding_time != "" else "10:00:00"
		context.wedding_iso = datetime.combine(getdate(self.wedding_date), get_time(wedding_time), tzinfo=ZoneInfo(self.timezone)).isoformat()
		context.rsvp_open = bool(self.enable_rsvp and (not self.rsvp_deadline or datetime.now(ZoneInfo(self.timezone)).date() <= getdate(self.rsvp_deadline)))
		context.csrf_token = frappe.sessions.get_csrf_token()

		if self.invitation_template == "Hindu Wedding":
			self.set_hindu_context(context)

	def set_hindu_context(self, context):
		# Only public presentation fields are serialized, never the whole document.
		fields = ("invitation_message", "bride_parents", "groom_parents", "hero_image",
			"couple_image", "quote", "travel_notes", "contact_name", "contact_phone",
			"contact_email", "music_file", "enable_rsvp", "rsvp_deadline", "max_guests", "rsvp_message")
		saved = {field: self.get(field) for field in fields}
		saved["rsvp_open"] = context.rsvp_open
		saved["story"] = [{key: row.get(key) for key in ("title", "milestone_date", "description", "image")} for row in self.story]
		saved["gallery"] = [{key: row.get(key) for key in ("image", "caption")} for row in self.gallery]
		saved["events"] = []
		for row in self.events:
			event = {key: row.get(key) for key in ("event_name", "venue_name", "address", "description", "dress_code", "maps_url")}
			event["date"] = get_datetime(row.event_datetime).replace(tzinfo=ZoneInfo(self.timezone)).isoformat()
			saved["events"].append(event)
		context.hindu_data = frappe.as_json({
			"groom": self.groom_name, "bride": self.bride_name, "weddingDate": context.wedding_iso,
			"timeZone": self.timezone, "invitationRoute": self.route, "saved": saved,
			"venue": self.events[0].venue_name if self.events else "",
			"city": self.events[0].address if self.events else "",
		})
		manifest_path = frappe.get_app_path("invite", "public", "frontend", ".vite", "manifest.json")
		with open(manifest_path) as manifest_file:
			manifest = json.load(manifest_file)
		entry = manifest["src/hindu.js"]
		context.hindu_script = "/assets/invite/frontend/" + entry["file"]
		styles = set()
		visited = set()
		def collect_styles(key):
			if key in visited:
				return
			visited.add(key)
			chunk = manifest[key]
			styles.update(chunk.get("css", []))
			for dependency in chunk.get("imports", []):
				collect_styles(dependency)
		collect_styles("src/hindu.js")
		context.hindu_styles = ["/assets/invite/frontend/" + path for path in sorted(styles)]
