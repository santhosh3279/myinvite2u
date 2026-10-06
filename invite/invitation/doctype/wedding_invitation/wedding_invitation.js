async function autofill_invitation_domain(frm) {
  const { bride_name, groom_name, invitation_domain } = frm.doc;
  if (!bride_name || !groom_name) return;
  // A host typed by the user takes precedence over the generated suggestion.
  if (invitation_domain && invitation_domain !== frm._suggested_invitation_domain) return;
  const { message: suggestion } = await frappe.call({
    method: 'invite.domains.suggest_invitation_domain',
    args: { bride_name, groom_name },
  });
  // Ignore responses from an earlier edit, including manual domain edits.
  if (frm.doc.bride_name !== bride_name || frm.doc.groom_name !== groom_name ||
      frm.doc.invitation_domain !== invitation_domain || !suggestion) return;
  frm._suggested_invitation_domain = suggestion;
  await frm.set_value('invitation_domain', suggestion);
}

frappe.ui.form.on('Wedding Invitation', {
  onload(frm) {
    frm._suggested_invitation_domain = frm.doc.__onload?.suggested_invitation_domain || '';
    return autofill_invitation_domain(frm);
  },
  bride_name: autofill_invitation_domain,
  groom_name: autofill_invitation_domain,
  enable_subdomain: autofill_invitation_domain,
  refresh(frm) {
    if (!frm.is_new() && frm.doc.route) {
      frm.add_custom_button(__('Open Invitation'), () => {
        window.open(frm.doc.public_url || '/' + frm.doc.route, '_blank', 'noopener');
      });
      frm.add_custom_button(__('View RSVPs'), () => {
        frappe.set_route('List', 'Wedding RSVP', { invitation: frm.doc.name });
      });
    }
  },
});
