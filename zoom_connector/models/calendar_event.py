
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
	_inherit = "calendar.event"

	# Campos para integración con Zoom
	zoom_meeting_id = fields.Many2one("zoom.meeting", string="Reunión Zoom", ondelete="cascade")
	is_zoom_meeting = fields.Boolean(string="Es Reunión Zoom", default=False)
	zoom_join_url = fields.Char(string="URL de Zoom", related="zoom_meeting_id.join_url", readonly=True)
	zoom_meeting_id_number = fields.Char(string="ID de Reunión Zoom", related="zoom_meeting_id.meeting_id", readonly=True)

	def action_join_zoom_meeting(self):
		"""Unirse a la reunión Zoom desde el calendario"""
		self.ensure_one()
		if not self.zoom_meeting_id or not self.zoom_meeting_id.join_url:
			raise UserError(_("No hay URL de Zoom disponible para esta reunión"))

		return {
			"type": "ir.actions.act_url",
			"url": self.zoom_meeting_id.join_url,
			"target": "new",
		}

	def action_show_zoom_buttons(self):
		"""Mostrar botones de Zoom en la vista de calendario"""
		self.ensure_one()
		if self.is_zoom_meeting and self.zoom_meeting_id:
			return {
				"type": "ir.actions.act_window",
				"name": _("Reunión Zoom"),
				"res_model": "calendar.event",
				"res_id": self.id,
				"view_mode": "form",
				"target": "new",
				"context": {
					"show_zoom_buttons": True,
				}
			}
		return False

	def action_start_zoom_meeting(self):
		"""Iniciar reunión Zoom desde el calendario"""
		self.ensure_one()
		if not self.zoom_meeting_id or not self.zoom_meeting_id.start_url:
			raise UserError(_("No hay URL de inicio disponible para esta reunión"))

		# Actualizar estado a activo
		self.zoom_meeting_id.status = "active"

		return {
			"type": "ir.actions.act_url",
			"url": self.zoom_meeting_id.start_url,
			"target": "new",
		}

	def action_create_zoom_meeting(self):
		"""Crear reunión Zoom desde evento de calendario"""
		self.ensure_one()

		if self.zoom_meeting_id:
			raise UserError(_("Este evento ya tiene una reunión Zoom asociada"))

		# Crear reunión Zoom
		meeting_data = {
			"name": self.name,
			"start_time": self.start,
			"duration": int(self.duration),
			"description": self.description or "",
			"participants": ",".join([p.email for p in self.partner_ids if p.email]),
		}

		try:
			# Obtener configuración de Zoom
			config = self.env["zoom.config"].get_active_config()
			if not config:
				raise UserError(_("No hay configuración de Zoom disponible"))

			# Crear reunión en Zoom
			zoom_result = config.create_zoom_meeting(meeting_data)

			# Crear registro de reunión en Odoo
			meeting = self.env["zoom.meeting"].create({
				"name": self.name,
				"meeting_id": zoom_result.get("id"),
				"start_time": self.start,
				"duration": int(self.duration),
				"description": self.description or "",
				"participants": ",".join([p.email for p in self.partner_ids if p.email]),
				"join_url": zoom_result.get("join_url"),
				"start_url": zoom_result.get("start_url"),
				"status": "scheduled",
				"calendar_event_id": self.id,
			})

			# Asociar la reunión con el evento
			self.zoom_meeting_id = meeting.id
			self.is_zoom_meeting = True

			return {
				"type": "ir.actions.client",
				"tag": "display_notification",
				"params": {
					"title": _("Reunión Zoom Creada"),
					"message": _("Se creó la reunión Zoom y se asoció con este evento."),
					"type": "success",
				}
			}

		except Exception as e:
			_logger.error(f"Error creando reunión Zoom desde calendario: {str(e)}")

	@api.model
	def create(self, vals):
		"""Override create para detectar eventos de Zoom"""
		event = super().create(vals)

		if self.env.context.get("skip_zoom_sync"):
			return event

		# Si el nombre contiene "Zoom" o "Reunión", marcar como reunión Zoom
		if event.name and ("zoom" in event.name.lower() or "reunión" in event.name.lower()):
			event.is_zoom_meeting = True

		return event

	def write(self, vals):
		"""Override write para sincronizar con Zoom"""
		result = super().write(vals)

		if self.env.context.get("skip_zoom_sync"):
			return result

		for event in self:
			if event.zoom_meeting_id and any(field in vals for field in ["name", "start", "duration", "description"]):
				# Sincronizar cambios con Zoom
				try:
					event.zoom_meeting_id.with_context(skip_zoom_sync=True).write({
						"name": event.name,
						"start_time": event.start,
						"duration": int(event.duration),
						"description": event.description or "",
					})
				except Exception as e:
					_logger.error(f"Error sincronizando evento con Zoom: {str(e)}")

		return result

	def unlink(self):
		"""Override unlink para eliminar reunión Zoom asociada"""
		if self.env.context.get("skip_zoom_sync"):
			return super().unlink()

		for event in self:
			if event.zoom_meeting_id:
				# Cancelar reunión en Zoom si es necesario
				try:
					if event.zoom_meeting_id.status in ["scheduled", "active"]:
						event.zoom_meeting_id.action_cancel_meeting()
				except Exception as e:
					_logger.error(f"Error cancelando reunión Zoom: {str(e)}")

				# Eliminar reunión de Odoo
				event.zoom_meeting_id.with_context(skip_zoom_sync=True).unlink()

		return super().unlink()

	def _get_base_url(self):
		"""Obtener URL base del sistema"""
		base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
		if not base_url:
			# Fallback compatible con Odoo.sh
			base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url.freeze") or "https://your-instance.odoo.com"
		return base_url
