
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ZoomDashboard(models.Model):
	_name = "zoom.dashboard"
	_description = "Dashboard de Zoom"

	# Campos para estadísticas
	total_meetings = fields.Integer("Total Reuniones", default=0)
	active_meetings = fields.Integer("Reuniones Activas", default=0)
	scheduled_meetings = fields.Integer("Reuniones Programadas", default=0)
	finished_meetings = fields.Integer("Reuniones Finalizadas", default=0)

	# Campos para información de configuración
	connection_status = fields.Char("Estado de Conexión", default="No configurado")
	last_sync = fields.Datetime("Última Sincronización", default=False)
	token_expires_in = fields.Char("Token Expira En", default="N/A")
	config_status_icon = fields.Char("Icono de Estado", default="fa-exclamation-triangle")
	config_status_color = fields.Char("Color de Estado", default="#dc3545")

	@api.model
	def default_get(self, fields_list):
		"""Calcular estadísticas y configuración por defecto"""
		res = super().default_get(fields_list)

		# Calcular estadísticas
		active_count = self.env["zoom.meeting"].search_count([("status", "=", "active")])
		scheduled_count = self.env["zoom.meeting"].search_count([("status", "=", "scheduled")])
		finished_count = self.env["zoom.meeting"].search_count([("status", "=", "finished")])
		total_count = self.env["zoom.meeting"].search_count([])

		res["active_meetings"] = active_count
		res["scheduled_meetings"] = scheduled_count
		res["finished_meetings"] = finished_count
		res["total_meetings"] = total_count

		# Obtener información de configuración
		config = self.env["zoom.config"].search([], limit=1)
		if config:
			res["connection_status"] = config.connection_status or "No configurado"
			res["last_sync"] = config.write_date  # Usar fecha de última modificación como última sincronización

			# Calcular tiempo restante del token
			if config.token_expires:
				now = fields.Datetime.now()
				if config.token_expires > now:
					time_diff = config.token_expires - now
					hours = int(time_diff.total_seconds() / 3600)
					minutes = int((time_diff.total_seconds() % 3600) / 60)
					if hours > 0:
						res["token_expires_in"] = f"{hours}h {minutes}m"
					else:
						res["token_expires_in"] = f"{minutes}m"
				else:
					res["token_expires_in"] = "Expirado"
			else:
				res["token_expires_in"] = "N/A"

			# Configurar icono y color según el estado
			if config.connection_status == "connected":
				res["config_status_icon"] = "fa-check-circle"
				res["config_status_color"] = "#28a745"
			elif config.connection_status == "error":
				res["config_status_icon"] = "fa-exclamation-triangle"
				res["config_status_color"] = "#dc3545"
			elif config.connection_status == "configured":
				res["config_status_icon"] = "fa-cog"
				res["config_status_color"] = "#17a2b8"
			else:
				res["config_status_icon"] = "fa-exclamation-triangle"
				res["config_status_color"] = "#dc3545"
		else:
			res["connection_status"] = "No configurado"
			res["last_sync"] = False
			res["token_expires_in"] = "N/A"
			res["config_status_icon"] = "fa-exclamation-triangle"
			res["config_status_color"] = "#dc3545"

		return res

	def action_create_quick_meeting(self):
		"""Crear una reunión rápida"""
		return {
			"type": "ir.actions.act_window",
			"name": "Crear Reunión Rápida",
			"res_model": "zoom.meeting",
			"view_mode": "form",
			"target": "new",
			"context": {
				"default_name": "Reunión Rápida",
				"default_status": "scheduled"
			}
		}

	def action_view_meetings(self):
		"""Ver todas las reuniones"""
		return {
			"type": "ir.actions.act_window",
			"name": "Reuniones Zoom",
			"res_model": "zoom.meeting",
			"view_mode": "list,form",
			"target": "current",
		}

	def action_view_active_meetings(self):
		"""Ver reuniones activas"""
		return {
			"type": "ir.actions.act_window",
			"name": "Reuniones Activas",
			"res_model": "zoom.meeting",
			"view_mode": "list,form",
			"target": "current",
			"domain": [("status", "=", "active")],
		}

	def action_view_calendar(self):
		"""Ver calendario nativo de Odoo con filtro para reuniones Zoom"""
		action = self.env.ref("zoom_connector.action_zoom_meeting_calendar").read()[0]
		action["target"] = "current"
		return action

	def action_open_config(self):
		"""Abrir configuración"""
		return {
			"type": "ir.actions.act_window",
			"name": "Configuración de Zoom",
			"res_model": "zoom.config",
			"view_mode": "form",
			"target": "current",
		}

	def action_sync_meetings(self):
		"""Sincronizar reuniones desde Zoom"""
		config = self.env["zoom.config"].get_active_config()
		if not config:
			raise UserError(_("No hay configuración de Zoom disponible. Por favor, configure las credenciales primero."))

		if not config.is_configured:
			raise UserError(_("La configuración de Zoom no está completa. Por favor, complete las credenciales y pruebe la conexión."))

		try:
			# Usar el método de sincronización corregido de zoom.config
			result = config.sync_meetings_manually()

			return {
				"type": "ir.actions.client",
				"tag": "display_notification",
				"params": {
					"title": _("Sincronización Exitosa"),
					"message": _("Reuniones sincronizadas correctamente desde Zoom."),
					"type": "success",
				}
			}
		except Exception as e:
			_logger.error(f"Error sincronizando reuniones: {str(e)}")
			raise UserError(_("Error al sincronizar reuniones: %s") % str(e))
