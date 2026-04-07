
import logging
from datetime import timedelta

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ZoomMeeting(models.Model):
	_name = "zoom.meeting"
	_description = "Reunión de Zoom"
	_order = "start_time desc"
	_rec_name = "name"

	name = fields.Char(
		string="Nombre de la Reunión",
		required=True,
		help="Nombre descriptivo de la reunión"
	)

	start_time = fields.Datetime(
		string="Fecha y Hora de Inicio",
		required=True,
		help="Fecha y hora programada para la reunión"
	)

	duration = fields.Integer(
		string="Duración (minutos)",
		default=60,
		readonly=True,
		help="Duración de la reunión en minutos (proporcionada por Zoom API)"
	)

	status = fields.Selection([
		("scheduled", "Programada"),
		("active", "En Curso"),
		("finished", "Finalizada"),
		("cancelled", "Cancelada"),
	], string="Estado", default="scheduled", tracking=True)

	description = fields.Text(
		string="Descripción",
		help="Descripción detallada de la reunión"
	)

	end_time = fields.Datetime(
		string="Fecha y Hora de Fin",
		compute="_compute_end_time",
		store=True,
		readonly=True,
		help="Fecha y hora real de finalización basada en la duración programada o proporcionada por Zoom"
	)

	participants = fields.Text(
		string="Participantes",
		help="Lista de participantes (emails separados por comas)"
	)

	expected_participants = fields.Integer(
		string="Participantes Esperados",
		default=1,
		help="Número estimado de participantes"
	)

	actual_participants = fields.Integer(
		string="Participantes Reales",
		help="Número real de participantes que se unieron"
	)

	meeting_id = fields.Char(
		string="ID de Reunión Zoom",
		help="Identificador único de la reunión en Zoom"
	)

	zoom_meeting_id = fields.Char(
		string="Zoom Meeting ID",
		compute="_compute_zoom_meeting_id",
		store=True,
		help="ID de la reunión en Zoom (alias de meeting_id)"
	)

	join_url = fields.Char(
		string="URL para Unirse",
		help="Enlace para unirse a la reunión"
	)

	start_url = fields.Char(
		string="URL para Iniciar",
		help="Enlace para iniciar la reunión (solo host)"
	)

	ticket_id = fields.Many2one(
		"helpdesk.ticket",
		string="Ticket",
		help="Ticket de Helpdesk relacionado con esta reunión"
	)

	team_id = fields.Many2one(
		"helpdesk.team",
		string="Equipo",
		related="ticket_id.team_id",
		store=True,
		help="Equipo de Helpdesk al que pertenece la reunión"
	)

	notes = fields.Text(
		string="Observaciones",
		help="Notas adicionales sobre la reunión"
	)

	calendar_event_id = fields.Many2one(
		"calendar.event",
		string="Evento de Calendario",
		help="Evento asociado en el calendario de Odoo"
	)

	zoom_created = fields.Boolean(
		string="Creada en Zoom",
		default=False,
		help="Indica si la reunión fue creada exitosamente en Zoom"
	)

	last_sync = fields.Datetime(
		string="Última Sincronización",
		help="Fecha y hora de la última sincronización con Zoom"
	)

	# === CAMPOS DE TIEMPO REAL (PARTE 2) ===
	actual_start_time = fields.Datetime(
		string="Inicio Real",
		readonly=True,
		help="Fecha y hora real de inicio de la reunión"
	)

	actual_end_time = fields.Datetime(
		string="Fin Real",
		readonly=True,
		help="Fecha y hora real de finalización de la reunión"
	)

	meeting_duration = fields.Integer(
		string="Duración Real (minutos)",
		readonly=True,
		compute="_compute_meeting_duration",
		store=True,
		help="Duración real de la reunión en minutos"
	)

	# === CAMPOS DE CONTROL DE INFORMACIÓN ===
	collaborators = fields.Text(
		string="Colaboradores",
		help="Lista de colaboradores externos que participaron"
	)

	internal_personnel = fields.Text(
		string="Personal Interno",
		help="Personal de la empresa que participó en la reunión"
	)

	session_url = fields.Char(
		string="URL de Sesión",
		readonly=True,
		help="URL de la sesión grabada o compartida"
	)

	total_meeting_time = fields.Float(
		string="Tiempo Total (horas)",
		readonly=True,
		compute="_compute_total_meeting_time",
		store=True,
		help="Tiempo total de la reunión en horas"
	)

	meeting_summary = fields.Text(
		string="Resumen de Reunión",
		help="Resumen de lo discutido en la reunión"
	)

	action_items = fields.Text(
		string="Elementos de Acción",
		help="Tareas o elementos de acción derivados de la reunión"
	)

	# === CAMPOS DE ASISTENTES (PARTE 3) ===
	attendee_ids = fields.One2many(
		"zoom.meeting.attendee",
		"meeting_id",
		string="Asistentes",
		help="Lista de asistentes invitados a la reunión"
	)

	total_invited = fields.Integer(
		string="Total Invitados",
		compute="_compute_attendance_stats",
		store=True,
		help="Número total de personas invitadas"
	)

	total_confirmed = fields.Integer(
		string="Total Confirmados",
		compute="_compute_attendance_stats",
		store=True,
		help="Número total de confirmaciones"
	)

	total_attended = fields.Integer(
		string="Total Asistieron",
		compute="_compute_attendance_stats",
		store=True,
		help="Número total de personas que asistieron"
	)

	attendance_rate = fields.Float(
		string="Tasa de Asistencia (%)",
		compute="_compute_attendance_stats",
		store=True,
		help="Porcentaje de asistencia basado en confirmaciones"
	)

	@api.depends("actual_start_time", "actual_end_time")
	def _compute_meeting_duration(self):
		"""Calcular duración real de la reunión"""
		for record in self:
			if record.actual_start_time and record.actual_end_time:
				duration = record.actual_end_time - record.actual_start_time
				record.meeting_duration = int(duration.total_seconds() / 60)
			else:
				record.meeting_duration = 0

	@api.depends("meeting_duration")
	def _compute_total_meeting_time(self):
		"""Calcular tiempo total en horas"""
		for record in self:
			if record.meeting_duration:
				record.total_meeting_time = record.meeting_duration / 60.0
			else:
				record.total_meeting_time = 0.0

	@api.depends("attendee_ids.status")
	def _compute_attendance_stats(self):
		"""Calcular estadísticas de asistencia"""
		for record in self:
			total_invited = len(record.attendee_ids)
			total_confirmed = len(record.attendee_ids.filtered(lambda a: a.status == "confirmed"))
			total_attended = len(record.attendee_ids.filtered(lambda a: a.status == "attended"))

			record.total_invited = total_invited
			record.total_confirmed = total_confirmed
			record.total_attended = total_attended

			# Calcular tasa de asistencia
			if total_invited > 0:
				record.attendance_rate = (total_confirmed / total_invited) * 100
			else:
				record.attendance_rate = 0.0

	def action_start_meeting_real(self):
		"""Marcar inicio real de la reunión"""
		self.ensure_one()
		current_time = fields.Datetime.now()

		# Actualizar los campos
		self.write({
			"actual_start_time": current_time,
			"status": "active"
		})

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Reunión Iniciada"),
				"message": _("Se ha registrado el inicio real de la reunión: %s") % current_time.strftime("%d/%m/%Y %H:%M:%S"),
				"type": "success",
			}
		}

	def action_end_meeting_real(self):
		"""Marcar fin real de la reunión"""
		self.ensure_one()
		if not self.actual_start_time:
			raise UserError(_("No se puede finalizar una reunión que no ha iniciado."))

		current_time = fields.Datetime.now()

		# Actualizar los campos
		self.write({
			"actual_end_time": current_time,
			"status": "finished"
		})

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Reunión Finalizada"),
				"message": _("Se ha registrado el fin real de la reunión: %s") % current_time.strftime("%d/%m/%Y %H:%M:%S"),
				"type": "success",
			}
		}

	def action_add_attendee(self):
		"""Agregar nuevo asistente"""
		self.ensure_one()
		return {
			"type": "ir.actions.act_window",
			"name": _("Agregar Asistente"),
			"res_model": "zoom.meeting.attendee",
			"view_mode": "form",
			"target": "new",
			"context": {
				"default_meeting_id": self.id,
				"default_status": "invited"
			}
		}

	def action_view_attendees(self):
		"""Ver lista de asistentes"""
		self.ensure_one()
		return {
			"type": "ir.actions.act_window",
			"name": _("Asistentes de la Reunión"),
			"res_model": "zoom.meeting.attendee",
			"view_mode": "list,form",
			"domain": [("meeting_id", "=", self.id)],
			"context": {
				"default_meeting_id": self.id
			}
		}

	def action_send_invitations(self):
		"""Enviar invitaciones a todos los asistentes"""
		self.ensure_one()
		if not self.attendee_ids:
			raise UserError(_("No hay asistentes para invitar."))

		sent_count = 0
		for attendee in self.attendee_ids:
			if attendee.status == "invited":
				try:
					attendee._send_invitation()
					sent_count += 1
				except Exception as e:
					_logger.warning(f"Error enviando invitación a {attendee.email}: {str(e)}")

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Invitaciones Enviadas"),
				"message": _("Se han enviado %d invitaciones") % sent_count,
				"type": "success",
			}
		}

	def action_mark_all_attended(self):
		"""Marcar todos los confirmados como asistieron"""
		self.ensure_one()
		confirmed_attendees = self.attendee_ids.filtered(lambda a: a.status == "confirmed")

		if not confirmed_attendees:
			raise UserError(_("No hay asistentes confirmados para marcar como asistieron."))

		for attendee in confirmed_attendees:
			attendee.action_mark_attended()

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Asistencia Registrada"),
				"message": _("Se ha registrado la asistencia de %d personas") % len(confirmed_attendees),
				"type": "success",
			}
		}

	# === MÉTODOS DE COPIA (PARTE 4) ===
	def action_copy_join_url(self):
		"""Copiar URL de unirse a la reunión al portapapeles"""
		self.ensure_one()
		if not self.join_url:
			raise UserError(_("No hay URL de unirse disponible para esta reunión."))

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("URL Copiada"),
				"message": _("URL de unirse copiada al portapapeles"),
				"type": "success",
				"sticky": False,
			}
		}

	def action_copy_start_url(self):
		"""Copiar URL de iniciar reunión al portapapeles"""
		self.ensure_one()
		if not self.start_url:
			raise UserError(_("No hay URL de iniciar disponible para esta reunión."))

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("URL Copiada"),
				"message": _("URL de iniciar copiada al portapapeles"),
				"type": "success",
				"sticky": False,
			}
		}

	def action_copy_meeting_id(self):
		"""Copiar Meeting ID al portapapeles"""
		self.ensure_one()
		if not self.meeting_id:
			raise UserError(_("No hay Meeting ID disponible para esta reunión."))

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Meeting ID Copiado"),
				"message": _("Meeting ID copiado al portapapeles"),
				"type": "success",
				"sticky": False,
			}
		}

	def action_copy_all_urls(self):
		"""Copiar todas las URLs e IDs al portapapeles"""
		self.ensure_one()

		urls_info = []
		if self.join_url:
			urls_info.append(f"URL de Unirse: {self.join_url}")
		if self.start_url:
			urls_info.append(f"URL de Iniciar: {self.start_url}")
		if self.meeting_id:
			urls_info.append(f"Meeting ID: {self.meeting_id}")

		if not urls_info:
			raise UserError(_("No hay URLs o IDs disponibles para copiar."))

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Información Copiada"),
				"message": _("Toda la información de la reunión ha sido copiada al portapapeles"),
				"type": "success",
				"sticky": False,
			}
		}

	# === MÉTODOS DE ESTADÍSTICAS (PARTE 5) ===
	def action_view_meeting_statistics(self):
		"""Ver estadísticas detalladas de la reunión"""
		self.ensure_one()
		return {
			"type": "ir.actions.act_window",
			"name": _("Estadísticas de la Reunión"),
			"res_model": "zoom.meeting",
			"res_id": self.id,
			"view_mode": "form",
			"target": "new",
			"context": {
				"default_name": self.name,
				"default_start_time": self.start_time,
				"default_total_invited": self.total_invited,
				"default_total_confirmed": self.total_confirmed,
				"default_total_attended": self.total_attended,
				"default_attendance_rate": self.attendance_rate,
			}
		}

	@api.model
	def get_meeting_statistics(self):
		"""Obtener estadísticas generales de todas las reuniones"""
		total_meetings = self.search_count([])
		scheduled_meetings = self.search_count([("status", "=", "scheduled")])
		active_meetings = self.search_count([("status", "=", "active")])
		finished_meetings = self.search_count([("status", "=", "finished")])
		cancelled_meetings = self.search_count([("status", "=", "cancelled")])

		# Estadísticas de asistencia
		meetings_with_attendees = self.search_count([("total_invited", ">", 0)])
		high_attendance_meetings = self.search_count([("attendance_rate", ">=", 80)])

		# Reuniones de hoy
		today_start = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
		today_end = fields.Datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
		today_meetings = self.search_count([
			("start_time", ">=", today_start),
			("start_time", "<=", today_end)
		])

		return {
			"total_meetings": total_meetings,
			"scheduled_meetings": scheduled_meetings,
			"active_meetings": active_meetings,
			"finished_meetings": finished_meetings,
			"cancelled_meetings": cancelled_meetings,
			"meetings_with_attendees": meetings_with_attendees,
			"high_attendance_meetings": high_attendance_meetings,
			"today_meetings": today_meetings,
		}

	# === MÉTODOS DE NOTIFICACIONES (PARTE 6) ===
	def _notify_organizer_attendance_update(self):
		"""Notificar al organizador sobre actualización de asistencia"""
		self.ensure_one()

		if not self.create_uid or not self.create_uid.email:
			_logger.warning(f"No email found for organizer {self.create_uid.name if self.create_uid else 'Unknown'}")
			return

		try:
			template = self.env.ref("zoom_connector.email_template_organizer_notification")
			template.send_mail(self.id, force_send=True)
			_logger.info(f"Organizer notification sent for meeting {self.name}")
		except Exception as e:
			_logger.error(f"Error sending organizer notification for meeting {self.name}: {str(e)}")

	def action_send_reminders(self):
		"""Enviar recordatorios a todos los asistentes confirmados"""
		self.ensure_one()

		confirmed_attendees = self.attendee_ids.filtered(lambda a: a.status == "confirmed")

		if not confirmed_attendees:
			raise UserError(_("No hay asistentes confirmados para enviar recordatorios."))

		sent_count = 0
		for attendee in confirmed_attendees:
			try:
				attendee._send_reminder()
				sent_count += 1
			except Exception as e:
				_logger.warning(f"Error enviando recordatorio a {attendee.email}: {str(e)}")

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Recordatorios Enviados"),
				"message": _("Se han enviado %d recordatorios") % sent_count,
				"type": "success",
			}
		}

	def action_send_meeting_summary(self):
		"""Enviar resumen de la reunión a todos los asistentes"""
		self.ensure_one()

		if not self.meeting_summary:
			raise UserError(_("No hay resumen de la reunión para enviar."))

		attended_attendees = self.attendee_ids.filtered(lambda a: a.status == "attended")

		if not attended_attendees:
			raise UserError(_("No hay asistentes que hayan participado en la reunión."))

		# Crear template personalizado para el resumen
		action_items_html = ""
		if self.action_items:
			action_items_html = f"""
                    <h3>Elementos de Acción:</h3>
                    <p>{self.action_items}</p>
                    <br/>"""

		template_data = {
			"name": f"Resumen de Reunión - {self.name}",
			"model_id": self.env.ref("zoom_connector.model_zoom_meeting").id,
			"subject": f"Resumen de Reunión: {self.name}",
			"email_from": self.create_uid.email_formatted,
			"body_html": f"""
                <div style="margin: 0px; padding: 0px; font-size: 13px;">
                    <p>Hola,</p>
                    <br/>
                    <p>Te enviamos el resumen de la reunión en la que participaste:</p>
                    <br/>
                    <div style="margin: 16px 0px 16px 0px; padding: 8px 16px 8px 16px; background-color: #f8f9fa; border-left: 4px solid #007bff;">
                        <p><strong>Reunión:</strong> {self.name}</p>
                        <p><strong>Fecha:</strong> {self.start_time.strftime('%d/%m/%Y a las %H:%M')}</p>
                        <p><strong>Duración:</strong> {self.meeting_duration} minutos</p>
                    </div>
                    <br/>
                    <h3>Resumen de la Reunión:</h3>
                    <p>{self.meeting_summary}</p>
                    <br/>
                    {action_items_html}
                    <p>Saludos cordiales,<br/>{self.create_uid.name}</p>
                </div>
            """,
			"auto_delete": True
		}

		template = self.env["mail.template"].create(template_data)

		sent_count = 0
		for attendee in attended_attendees:
			try:
				template.write({"email_to": attendee.email})
				template.send_mail(self.id, force_send=True)
				sent_count += 1
			except Exception as e:
				_logger.warning(f"Error enviando resumen a {attendee.email}: {str(e)}")

		# Eliminar template temporal
		template.unlink()

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Resumen Enviado"),
				"message": _("Se ha enviado el resumen a %d asistentes") % sent_count,
				"type": "success",
			}
		}

	@api.model
	def _send_automatic_reminders(self):
		"""Enviar recordatorios automáticos (llamado por cron job)"""
		# Buscar reuniones que empiecen en 1 hora
		one_hour_from_now = fields.Datetime.now() + timedelta(hours=1)
		one_hour_plus_30min = one_hour_from_now + timedelta(minutes=30)

		meetings_to_remind = self.search([
			("status", "=", "scheduled"),
			("start_time", ">=", one_hour_from_now),
			("start_time", "<=", one_hour_plus_30min),
		])

		total_reminders_sent = 0
		for meeting in meetings_to_remind:
			confirmed_attendees = meeting.attendee_ids.filtered(lambda a: a.status == "confirmed")

			for attendee in confirmed_attendees:
				try:
					attendee._send_reminder()
					total_reminders_sent += 1
				except Exception as e:
					_logger.error(f"Error sending automatic reminder to {attendee.email}: {str(e)}")

		if total_reminders_sent > 0:
			_logger.info(f"Automatic reminders sent: {total_reminders_sent} reminders for {len(meetings_to_remind)} meetings")

		return total_reminders_sent

	def create_zoom_meeting(self, meeting_data=None):
		"""Crear reunión en Zoom API"""
		self.ensure_one()
		try:
			config = self.env["zoom.config"].get_config()
			if not config:
				raise UserError(_("Configuración de Zoom no encontrada"))

			# Obtener token si es necesario
			if not config.access_token or (config.token_expires and config.token_expires <= fields.Datetime.now()):
				config._get_access_token()

			headers = {
				"Authorization": f"Bearer {config.access_token}",
				"Content-Type": "application/json"
			}

			# Preparar datos para Zoom API
			if not meeting_data:
				meeting_data = {
					"name": self.name,
					"start_time": self.start_time.isoformat(),
					"duration": self.duration
				}

			zoom_data = {
				"topic": meeting_data.get("name", self.name),
				"type": 2,  # Reunión programada
				"start_time": meeting_data.get("start_time", self.start_time.isoformat()),
				"duration": meeting_data.get("duration", self.duration),
				"timezone": "America/Lima",
				"settings": {
					"host_video": True,
					"participant_video": True,
					"join_before_host": config.join_before_host,
					"mute_upon_entry": config.mute_on_entry,
					"waiting_room": config.waiting_room,
					"auto_recording": "local" if config.auto_record else "none",
				}
			}

			response = requests.post(
				f"{config.base_url}/users/me/meetings",
				headers=headers,
				json=zoom_data,
				timeout=30
			)

			if response.status_code == 201:
				meeting_info = response.json()
				result = {
					"meeting_id": str(meeting_info.get("id")),
					"join_url": meeting_info.get("join_url"),
					"start_url": meeting_info.get("start_url"),
					"zoom_created": True,
					"last_sync": fields.Datetime.now()
				}

				# Actualizar el registro
				self.write(result)
				return result
			else:
				_logger.error(f"Error creando reunión en Zoom: {response.text}")
				raise UserError(_("Error al crear reunión en Zoom: %s") % response.text)

		except requests.exceptions.RequestException as e:
			_logger.error(f"Error de conexión con Zoom: {str(e)}")
			raise UserError(_("Error de conexión con Zoom: %s") % str(e))
		except Exception as e:
			_logger.error(f"Error inesperado: {str(e)}")
			raise UserError(_("Error inesperado: %s") % str(e))

	def create_instant_meeting(self):
		"""Crear reunión instantánea"""
		self.ensure_one()
		try:
			config = self.env["zoom.config"].get_config()
			if not config:
				raise UserError(_("Configuración de Zoom no encontrada"))

			# Obtener token si es necesario
			if not config.access_token or (config.token_expires and config.token_expires <= fields.Datetime.now()):
				config._get_access_token()

			headers = {
				"Authorization": f"Bearer {config.access_token}",
				"Content-Type": "application/json"
			}

			zoom_data = {
				"topic": self.name or f'Reunión Instantánea - {self.ticket_id.name if self.ticket_id else "Odoo"}',
				"type": 1,  # Reunión instantánea
				"settings": {
					"host_video": True,
					"participant_video": True,
					"join_before_host": config.join_before_host,
					"mute_upon_entry": config.mute_on_entry,
					"waiting_room": config.waiting_room,
					"auto_recording": "local" if config.auto_record else "none",
				}
			}

			response = requests.post(
				f"{config.base_url}/users/me/meetings",
				headers=headers,
				json=zoom_data,
				timeout=30
			)

			if response.status_code == 201:
				meeting_info = response.json()
				self.write({
					"meeting_id": str(meeting_info.get("id")),
					"join_url": meeting_info.get("join_url"),
					"start_url": meeting_info.get("start_url"),
					"status": "active",
					"zoom_created": True,
					"last_sync": fields.Datetime.now()
				})

				# Crear evento en calendario
				self._create_calendar_event()

				return {
					"type": "ir.actions.act_url",
					"url": self.start_url,
					"target": "new",
				}
			else:
				raise UserError(_("Error al crear reunión instantánea: %s") % response.text)

		except Exception as e:
			_logger.error(f"Error creando reunión instantánea: {str(e)}")
			raise UserError(_("Error: %s") % str(e))

	def _create_calendar_event(self):
		"""Crear evento en calendario de Odoo"""
		if not self.calendar_event_id and self.start_time:
			# Obtener participantes si están definidos
			partner_ids = []
			if self.participants:
				emails = [email.strip() for email in self.participants.split(",") if email.strip()]
				for email in emails:
					partner = self.env["res.partner"].search([("email", "=", email)], limit=1)
					if partner:
						partner_ids.append(partner.id)
					else:
						# Crear partner si no existe
						partner = self.env["res.partner"].create({
							"name": email,
							"email": email,
							"is_company": False
						})
						partner_ids.append(partner.id)

			# Asegurar que el usuario actual esté incluido para que vea el evento
			current_partner = self.env.user.partner_id
			if current_partner and current_partner.id not in partner_ids:
				partner_ids.append(current_partner.id)

			event = self.env["calendar.event"].with_context(skip_zoom_sync=True).create({
				"name": self.name,
				"start": self.start_time,
				"stop": self.end_time or self.start_time,
				"duration": (self.duration or 0) / 60.0,
				"description": self.description or f'Reunión Zoom: {self.name}\n\nURL para unirse: {self.join_url or "No disponible"}',
				"location": f"Zoom Meeting ID: {self.meeting_id}",
				"user_id": self.env.user.id,
				"partner_ids": [(6, 0, partner_ids)],
				"allday": False,
				"show_as": "busy",
				"zoom_meeting_id": self.id,
				"is_zoom_meeting": True,
			})
			self.calendar_event_id = event.id
			_logger.info(f"Evento de calendario creado: {event.id} para reunión {self.id}")

	def _update_calendar_event(self):
		"""Actualizar evento de calendario existente"""
		if self.calendar_event_id:
			partner_ids = []
			if self.participants:
				emails = [email.strip() for email in self.participants.split(",") if email.strip()]
				for email in emails:
					partner = self.env["res.partner"].search([("email", "=", email)], limit=1)
					if partner:
						partner_ids.append(partner.id)
					else:
						partner = self.env["res.partner"].create({
							"name": email,
							"email": email,
							"is_company": False
						})
						partner_ids.append(partner.id)

			current_partner = self.env.user.partner_id
			if current_partner and current_partner.id not in partner_ids:
				partner_ids.append(current_partner.id)

			self.calendar_event_id.with_context(skip_zoom_sync=True).write({
				"name": self.name,
				"start": self.start_time,
				"stop": self.end_time or self.start_time,
				"duration": (self.duration or 0) / 60.0,
				"description": self.description or f'Reunión Zoom: {self.name}\n\nURL para unirse: {self.join_url or "No disponible"}',
				"location": f"Zoom Meeting ID: {self.meeting_id}",
				"zoom_meeting_id": self.id,
				"is_zoom_meeting": True,
				"partner_ids": [(6, 0, partner_ids)] if partner_ids else False,
			})
			_logger.info(f"Evento de calendario actualizado: {self.calendar_event_id.id}")

	def _delete_calendar_event(self):
		"""Eliminar evento de calendario"""
		if self.calendar_event_id:
			event_id = self.calendar_event_id.id
			self.calendar_event_id.with_context(skip_zoom_sync=True).unlink()
			self.calendar_event_id = False
			_logger.info(f"Evento de calendario eliminado: {event_id}")

	def action_regenerate_calendar_events(self):
		"""Crear o actualizar eventos de calendario para las reuniones seleccionadas"""
		meetings = self
		if not meetings:
			meetings = self.search([])

		for meeting in meetings:
			if not meeting.start_time:
				continue

			if meeting.calendar_event_id:
				meeting._update_calendar_event()
			else:
				meeting._create_calendar_event()

		action = self.env.ref("zoom_connector.action_calendar_event_zoom").read()[0]
		return action

	@api.model
	def create(self, vals):
		"""Override create para manejar calendario y sincronizar con Zoom"""
		meeting = super().create(vals)

		if meeting.start_time and meeting.duration:
			meeting._create_calendar_event()

		should_auto_create_zoom = (
				not self.env.context.get("skip_zoom_creation")
				and not meeting.zoom_created
				and meeting.start_time
				and meeting.duration
		)

		if should_auto_create_zoom:
			try:
				meeting.create_zoom_meeting()
			except UserError:
				raise
			except Exception as e:
				_logger.error("Error creando reunión Zoom al crear %s: %s", meeting.id, e)
				raise

		return meeting

	def write(self, vals):
		"""Override write para manejar calendario"""
		result = super().write(vals)
		for meeting in self:
			if any(field in vals for field in ["name", "start_time", "duration", "description", "meeting_id", "join_url"]):
				if meeting.calendar_event_id:
					meeting._update_calendar_event()
				elif meeting.start_time and meeting.duration:
					meeting._create_calendar_event()
		return result

	def unlink(self):
		"""Override unlink para eliminar eventos de calendario"""
		for meeting in self:
			meeting._delete_calendar_event()
		return super().unlink()

	def action_start_meeting(self):
		"""Acción para iniciar reunión"""
		self.ensure_one()
		if not self.start_url:
			raise UserError(_("No hay URL de inicio disponible para esta reunión"))

		# Actualizar estado a activo
		self.status = "active"

		return {
			"type": "ir.actions.act_url",
			"url": self.start_url,
			"target": "new",
		}

	def action_join_meeting(self):
		"""Acción para unirse a reunión"""
		self.ensure_one()
		if not self.join_url:
			raise UserError(_("No hay URL de unión disponible para esta reunión"))

		return {
			"type": "ir.actions.act_url",
			"url": self.join_url,
			"target": "new",
		}

	def action_create_instant_meeting(self):
		"""Crear reunión instantánea desde dashboard"""
		meeting = self.create({
			"name": f'Reunión Instantánea - {fields.Datetime.now().strftime("%H:%M")}',
			"start_time": fields.Datetime.now(),
			"duration": 60,
			"status": "scheduled",
		})

		try:
			return meeting.create_instant_meeting()
		except Exception as e:
			_logger.error(f"Error creando reunión instantánea: {str(e)}")
			raise UserError(_("Error al crear reunión instantánea: %s") % str(e))

	def action_schedule_meeting(self):
		"""Programar reunión desde dashboard"""
		return {
			"type": "ir.actions.act_window",
			"name": _("Programar Reunión"),
			"res_model": "zoom.meeting",
			"view_mode": "form",
			"target": "new",
			"context": {
				"default_name": "Nueva Reunión Programada",
				"default_start_time": fields.Datetime.now() + timedelta(hours=1),
				"default_status": "scheduled"
			}
		}

	def action_open_config(self):
		"""Abrir configuración de Zoom"""
		return {
			"type": "ir.actions.act_window",
			"name": _("Configuración de Zoom"),
			"res_model": "zoom.config",
			"view_mode": "form",
			"target": "current",
			"context": {}
		}

	def action_view_meetings(self):
		"""Ver todas las reuniones"""
		return {
			"type": "ir.actions.act_window",
			"name": _("Reuniones"),
			"res_model": "zoom.meeting",
			"view_mode": "list,form",
			"target": "current",
			"context": {}
		}

	def action_view_active_meetings(self):
		"""Ver reuniones activas"""
		return {
			"type": "ir.actions.act_window",
			"name": _("Reuniones Activas"),
			"res_model": "zoom.meeting",
			"view_mode": "list,form",
			"domain": [("status", "=", "active")],
			"target": "current",
			"context": {}
		}

	def action_view_calendar(self):
		"""Ver calendario de reuniones"""
		return {
			"type": "ir.actions.act_window",
			"name": _("Calendario de Reuniones"),
			"res_model": "zoom.meeting",
			"view_mode": "calendar,list,form",
			"target": "current",
			"context": {}
		}

	def action_cancel_meeting(self):
		"""Cancelar reunión en Zoom"""
		self.ensure_one()
		if not self.meeting_id or not self.zoom_created:
			self.status = "cancelled"
			return

		try:
			config = self.env["zoom.config"].get_config()
			if not config:
				self.status = "cancelled"
				return

			headers = {
				"Authorization": f"Bearer {config.access_token}",
			}

			response = requests.delete(
				f"{config.base_url}/meetings/{self.meeting_id}",
				headers=headers,
				timeout=30
			)

			if response.status_code in [200, 204]:
				self.status = "cancelled"
				# Eliminar evento de calendario
				if self.calendar_event_id:
					self.calendar_event_id.unlink()
			else:
				_logger.warning(f"No se pudo cancelar reunión en Zoom: {response.text}")
				self.status = "cancelled"

		except Exception as e:
			_logger.error(f"Error cancelando reunión: {str(e)}")
			self.status = "cancelled"

	@api.model
	def update_meeting_status(self, meeting_id, status):
		"""Actualizar estado de reunión desde webhook"""
		meeting = self.search([("meeting_id", "=", str(meeting_id))])
		if meeting:
			status_map = {
				"meeting.started": "active",
				"meeting.ended": "finished",
				"meeting.cancelled": "cancelled",
			}
			new_status = status_map.get(status, meeting.status)
			meeting.write({
				"status": new_status,
				"last_sync": fields.Datetime.now()
			})
