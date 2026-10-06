import re
import unicodedata

import frappe
from frappe import _
from frappe.website.page_renderers.document_page import DocumentPage
from frappe.website.page_renderers.not_found_page import NotFoundPage


RESERVED_SUBDOMAINS = {"www", "app", "admin", "api", "mail", "smtp", "ftp", "autodiscover"}


def base_domain():
	return (frappe.conf.get("invitation_base_domain") or "myinvite2u.in").lower().strip(".")


def domain_from_names(bride_name, groom_name):
	def slug(value):
		value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
		return re.sub(r"[^a-z0-9]+", "-", value).strip("-")

	bride, groom = slug(bride_name), slug(groom_name)
	if not bride or not groom:
		return ""
	label = f"{bride[:30].rstrip('-')}-{groom[:30].rstrip('-')}"
	return f"{label}.{base_domain()}"


@frappe.whitelist()
def suggest_invitation_domain(bride_name="", groom_name=""):
	return domain_from_names(bride_name, groom_name)


def validate_invitation_domain(domain):
	domain = (domain or "").strip().lower()
	base = base_domain()
	suffix = "." + base
	if not domain.endswith(suffix):
		frappe.throw(_("Custom Domain must be a subdomain of {0}.").format(base))
	label = domain[:-len(suffix)]
	if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) or len(domain) > 140:
		frappe.throw(_("Use one subdomain label containing letters, numbers and hyphens, without a scheme, path or port."))
	if label in RESERVED_SUBDOMAINS:
		frappe.throw(_("This subdomain is reserved. Please choose another name."))
	return domain


def request_hostname():
	request = getattr(frappe.local, "request", None)
	return request.host.split(":", 1)[0].lower().rstrip(".") if request else ""


def is_invitation_host(hostname):
	return hostname.endswith("." + base_domain()) and hostname != "www." + base_domain()


def invitation_for_host(hostname):
	return frappe.db.get_value("Wedding Invitation", {
		"invitation_domain": hostname, "enable_subdomain": 1, "is_published": 1,
	}, ["name", "route"], as_dict=True)


class InvitationDomainPage(DocumentPage):
	"""Render a published invitation at its assigned hostname's root."""

	def can_render(self):
		hostname = request_hostname()
		if not is_invitation_host(hostname):
			return False
		self.invitation = invitation_for_host(hostname)
		# Read the original URL; Frappe resolves / to its configured home page first.
		requested_path = frappe.local.request.path.strip("/")
		self.found = bool(self.invitation and requested_path in ("", self.invitation.route))
		if self.found:
			self.doctype = "Wedding Invitation"
			self.docname = self.invitation.name
			# Use the unique record route for Frappe's renderer context/cache keys.
			self.path = self.invitation.route
		return True

	def render(self):
		if not self.found:
			return NotFoundPage(self.path).render()
		return super().render()
