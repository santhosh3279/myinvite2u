from datetime import datetime
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate, validate_email_address

from invite.domains import invitation_for_host, is_invitation_host, request_hostname


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=3600)
def submit_rsvp(route, guest_name, email, attendance, guest_count=1, phone="", dietary_requirements="", message="", website=""):
	if website:
		frappe.throw(_("Unable to submit RSVP."))
	name = frappe.db.get_value("Wedding Invitation", {"route": route, "is_published": 1}, "name")
	if not name:
		frappe.throw(_("Invitation not found."), frappe.DoesNotExistError)
	hostname = request_hostname()
	if is_invitation_host(hostname):
		assigned = invitation_for_host(hostname)
		if not assigned or assigned.name != name:
			frappe.throw(_("Invitation not found."), frappe.DoesNotExistError)
	invitation = frappe.get_doc("Wedding Invitation", name)
	if not invitation.enable_rsvp:
		frappe.throw(_("RSVP is closed for this invitation."))
	if invitation.rsvp_deadline and datetime.now(ZoneInfo(invitation.timezone)).date() > getdate(invitation.rsvp_deadline):
		frappe.throw(_("The RSVP deadline has passed."))
	guest_name = str(guest_name or "").strip()
	email = str(email or "").strip().lower()
	if not guest_name or len(guest_name) > 140:
		frappe.throw(_("Please enter your name (up to 140 characters)."))
	if not email or len(email) > 140:
		frappe.throw(_("Please enter your email address."))
	validate_email_address(email, throw=True)
	if attendance not in ("Attending", "Not Attending"):
		frappe.throw(_("Please choose your attendance."))
	try:
		count = int(str(guest_count))
	except (ValueError, TypeError):
		frappe.throw(_("Please enter a whole number of guests."))
	if attendance == "Attending" and not 1 <= count <= invitation.max_guests:
		frappe.throw(_("Guest count must be between 1 and {0}.").format(invitation.max_guests))
	for value, limit in ((phone, 40), (dietary_requirements, 1000), (message, 2000)):
		if len(str(value or "")) > limit:
			frappe.throw(_("Your response is too long."))
	frappe.get_doc({
		"doctype": "Wedding RSVP", "invitation": name, "guest_name": guest_name,
		"email": email, "phone": phone, "attendance": attendance,
		"guest_count": count if attendance == "Attending" else 0,
		"dietary_requirements": dietary_requirements, "message": message,
	}).insert(ignore_permissions=True)
	return {"success": True}
