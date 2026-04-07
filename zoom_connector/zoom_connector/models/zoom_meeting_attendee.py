
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ZoomMeetingAttendee(models.Model):
	_name = "zoom.meeting.attendee"
	_description = "Asistente de Reunión Zoom"
	_rec_name = "email"

	meeting_id = fields.Many2one(
		"zoom.meeting",
		string="Reunión",
		required=True,
		ondelete="cascade"
	)

	email = fields.Char(
		string="Email",
		required=True,
		help="Dirección de email del asistente"
	)

	name = fields.Char(
		string="Nombre",
		help="Nombre completo del asistente"
	)

	status = fields.Selection([
		("invited", "Invitado"),
		("confirmed", "Confirmado"),
		("declined", "Rechazado"),
		("attended", "Asistió"),
		("no_show", "No Asistió")
	], string="Estado", default="invited", required=True)

	invitation_sent = fields.Datetime(
		string="Invitación Enviada",
		readonly=True,
		help="Fecha y hora cuando se envió la invitación"
	)

	confirmation_date = fields.Datetime(
		string="Fecha de Confirmación",
		readonly=True,
		help="Fecha y hora cuando confirmó o rechazó la asistencia"
	)

	response_notes = fields.Text(
		string="Notas de Respuesta",
		help="Comentarios adicionales del asistente"
	)

	# Campos computados
	is_confirmed = fields.Boolean(
		string="Confirmado",
		compute="_compute_is_confirmed",
		store=True
	)

	is_attended = fields.Boolean(
		string="Asistió",
		compute="_compute_is_attended",
		store=True
	)

	@api.depends("status")
	def _compute_is_confirmed(self):
		for record in self:
			record.is_confirmed = record.status == "confirmed"

	@api.depends("status")
	def _compute_is_attended(self):
		for record in self:
			record.is_attended = record.status == "attended"

	@api.model
	def create(self, vals):
		"""Crear asistente y enviar invitación automáticamente"""
		attendee = super().create(vals)

		# Enviar invitación automáticamente
		if attendee.meeting_id:
			attendee._send_invitation()

		return attendee

	def _send_invitation(self):
		"""Enviar invitación por email al asistente"""
		self.ensure_one()

		if not self.email:
			raise UserError(_("No se puede enviar invitación sin email."))

		# Crear template de email
		template = self.env.ref("zoom_connector.email_template_meeting_invitation", False)
		if not template:
			# Crear template básico si no existe
			template = self._create_invitation_template()

		# Enviar email
		try:
			template.send_mail(self.id, force_send=True)
			self.write({
				"invitation_sent": fields.Datetime.now(),
				"status": "invited"
			})
		except Exception as e:
			raise UserError(_("Error enviando invitación: %s") % str(e))

	def _send_reminder(self):
		"""Enviar recordatorio por email"""
		self.ensure_one()

		if not self.email:
			raise UserError(_("No se puede enviar recordatorio sin email."))

		try:
			template = self.env.ref("zoom_connector.email_template_meeting_reminder")
			template.send_mail(self.id, force_send=True)
			_logger.info(f"Reminder sent to {self.email} for meeting {self.meeting_id.name}")
		except Exception as e:
			_logger.error(f"Error sending reminder to {self.email}: {str(e)}")
			raise UserError(_("Error enviando recordatorio: %s") % str(e))

	def _send_confirmation(self):
		"""Enviar confirmación de asistencia por email"""
		self.ensure_one()

		if not self.email:
			raise UserError(_("No se puede enviar confirmación sin email."))

		try:
			template = self.env.ref("zoom_connector.email_template_attendance_confirmation")
			template.send_mail(self.id, force_send=True)
			_logger.info(f"Confirmation sent to {self.email} for meeting {self.meeting_id.name}")
		except Exception as e:
			_logger.error(f"Error sending confirmation to {self.email}: {str(e)}")
			raise UserError(_("Error enviando confirmación: %s") % str(e))

	def _create_invitation_template(self):
		"""Crear template de invitación básico"""
		template = self.env["mail.template"].create({
			"name": "Invitación a Reunión Zoom",
			"model_id": self.env.ref("zoom_connector.model_zoom_meeting_attendee").id,
			"subject": "Invitación a Reunión: ${object.meeting_id.name}",
			"body_html": (
				'<div style="margin:0;padding:0;font-size:13px;">'
				'<p>Hola ${object.name or "Estimado/a"},</p>'
				'<p>Has sido invitado/a a la siguiente reunión:</p>'
				'<div style="background-color:#f8f9fa;padding:15px;border-radius:5px;margin:15px 0;">'
				'<h3>${object.meeting_id.name}</h3>'
				'<p><strong>Fecha y Hora:</strong> ${format_datetime(object.meeting_id.start_time, tz=user.tz, lang=user.lang)}</p>'
				'<p><strong>Duración:</strong> ${object.meeting_id.duration} minutos</p>'
				'% if object.meeting_id.description:\n'
				'<p><strong>Descripción:</strong> ${object.meeting_id.description}</p>'
				'% endif\n'
				'</div>'
				'<p>Por favor, confirma tu asistencia haciendo clic en uno de los siguientes enlaces:</p>'
				'<div style="margin:20px 0;">'
				'<a href="${object._get_confirmation_url(\'confirmed\')}" '
				'style="background-color:#28a745;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;margin-right:10px;">'
				'✅ Confirmar Asistencia</a>'
				'<a href="${object._get_confirmation_url(\'declined\')}" '
				'style="background-color:#dc3545;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">'
				'❌ Rechazar Invitación</a>'
				'</div>'
				'<p>Gracias por tu atención.</p>'
				'<hr style="margin:20px 0;border:none;border-top:1px solid #eee;"/>'
				'<p style="font-size:12px;color:#666;">Este es un mensaje automático del sistema de reuniones Zoom.</p>'
				'</div>'
			),
			"auto_delete": False,
		})
		return template

	def _get_confirmation_url(self, status):
		"""Generar URL de confirmación"""
		self.ensure_one()
		base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
		if not base_url:
			# Fallback compatible con Odoo.sh
			base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url.freeze") or "https://your-instance.odoo.com"
		return f"{base_url}/zoom/confirm/{self.id}/{status}"

	def action_confirm_attendance(self):
		"""Confirmar asistencia manualmente"""
		self.ensure_one()
		self.write({
			"status": "confirmed",
			"confirmation_date": fields.Datetime.now()
		})

		# Enviar confirmación por email
		self._send_confirmation()

		# Notificar al organizador
		self.meeting_id._notify_organizer_attendance_update()

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Asistencia Confirmada"),
				"message": _("Se ha confirmado la asistencia de %s y se ha enviado confirmación por email") % self.email,
				"type": "success",
			}
		}

	def action_mark_attended(self):
		"""Marcar como asistió"""
		self.ensure_one()
		if self.status != "confirmed":
			raise UserError(_("Solo se puede marcar como asistió a quien confirmó previamente."))

		self.write({
			"status": "attended",
			"confirmation_date": fields.Datetime.now()
		})
		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Asistencia Registrada"),
				"message": _("Se ha registrado la asistencia de %s") % self.email,
				"type": "success",
			}
		}

	def action_mark_no_show(self):
		"""Marcar como no asistió"""
		self.ensure_one()
		self.write({
			"status": "no_show",
			"confirmation_date": fields.Datetime.now()
		})
		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("No Asistencia Registrada"),
				"message": _("Se ha registrado que %s no asistió") % self.email,
				"type": "warning",
			}
		}

	def action_resend_invitation(self):
		"""Reenviar invitación"""
		self.ensure_one()
		self._send_invitation()
		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Invitación Reenviada"),
				"message": _("Se ha reenviado la invitación a %s") % self.email,
				"type": "success",
			}
		}

	def action_send_reminder(self):
		"""Enviar recordatorio por email (método público para botones)"""
		self.ensure_one()
		self._send_reminder()
		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Recordatorio Enviado"),
				"message": _("Se ha enviado el recordatorio a %s") % self.email,
				"type": "success",
			}
		}
