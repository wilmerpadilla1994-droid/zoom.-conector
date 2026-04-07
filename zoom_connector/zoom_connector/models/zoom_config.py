
import logging
from datetime import datetime, timedelta

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ZoomConfig(models.Model):
	_name = "zoom.config"
	_description = "Configuración de Zoom"
	_rec_name = "client_id"

	client_id = fields.Char(
		string="Client ID (API Key)",
		required=True,
		help="Client ID de la aplicación Zoom"
	)

	client_secret = fields.Char(
		string="Client Secret (API Secret)",
		required=True,
		help="Client Secret de la aplicación Zoom"
	)

	account_id = fields.Char(
		string="Account ID",
		required=True,
		help="Account ID de Zoom"
	)

	webhook_secret = fields.Char(
		string="Webhook Secret",
		required=False,
		help="Token secreto para validar webhooks"
	)

	use_webhooks = fields.Boolean(
		string="Usar Webhooks",
		default=False,
		help="Activar solo si tienes un dominio público configurado"
	)

	base_url = fields.Char(
		string="Base URL",
		default="https://api.zoom.us/v2",
		required=True,
		help="URL base de la API de Zoom"
	)

	auto_record = fields.Boolean(
		string="Grabación Automática",
		default=False,
		help="Grabar automáticamente las reuniones"
	)

	waiting_room = fields.Boolean(
		string="Sala de Espera",
		default=True,
		help="Activar sala de espera por defecto"
	)

	join_before_host = fields.Boolean(
		string="Unirse Antes del Host",
		default=False,
		help="Permitir que los participantes se unan antes del host"
	)

	mute_on_entry = fields.Boolean(
		string="Silenciar al Entrar",
		default=True,
		help="Silenciar automáticamente a los participantes al entrar"
	)

	access_token = fields.Char(
		string="Access Token",
		help="Token de acceso para la API de Zoom"
	)

	refresh_token = fields.Char(
		string="Refresh Token",
		help="Token de renovación para la API de Zoom"
	)

	token_expires = fields.Datetime(
		string="Token Expira",
		help="Fecha y hora de expiración del token"
	)

	is_configured = fields.Boolean(
		string="Configurado",
		compute="_compute_is_configured",
		help="Indica si la configuración está completa"
	)

	config_status = fields.Char(
		string="Estado de Configuración",
		compute="_compute_config_status",
		help="Estado actual de la configuración"
	)

	connection_status = fields.Selection([
		("not_configured", "No Configurado"),
		("configured", "Configurado"),
		("connected", "Conectado"),
		("error", "Error de Conexión"),
	], string="Estado de Conexión", default="not_configured", help="Estado actual de la conexión con Zoom")

	@api.depends("client_id", "client_secret", "account_id", "connection_status")
	def _compute_is_configured(self):
		"""Calcular si la configuración está completa"""
		for record in self:
			has_credentials = bool(
				record.client_id and
				record.client_secret and
				record.account_id
			)

			# Solo considerar configurado si tiene credenciales Y está conectado
			record.is_configured = has_credentials and record.connection_status == "connected"

			# Si no tiene credenciales, resetear el estado de conexión
			if not has_credentials and record.connection_status != "not_configured":
				record.connection_status = "not_configured"

	@api.depends("is_configured", "connection_status", "access_token", "token_expires")
	def _compute_config_status(self):
		"""Calcular el estado de configuración"""
		for record in self:
			if not record.is_configured:
				record.config_status = "⚠️ Configuración Pendiente - Complete las credenciales"
			elif record.connection_status == "connected" and record.access_token:
				# Verificar si el token está expirado
				if record.token_expires and record.token_expires <= fields.Datetime.now():
					record.config_status = "🔄 Token Expirado - Renovar conexión"
				else:
					record.config_status = "✅ Configuración Activa - Conectado a Zoom"
			elif record.connection_status == "configured":
				record.config_status = "🔧 Configuración Completa - Pruebe la conexión"
			elif record.connection_status == "error":
				record.config_status = "❌ Error de Conexión - Verifique las credenciales"
			elif record.connection_status == "not_configured":
				record.config_status = "⚠️ Configuración Pendiente - Complete las credenciales"
			else:
				record.config_status = "❌ Estado Desconocido - Verifique la configuración"

	def save_credentials(self):
		"""Guardar credenciales y actualizar estado"""
		self.ensure_one()

		# Validar que todos los campos requeridos estén llenos
		if not self.client_id or not self.client_secret or not self.account_id:
			raise UserError(_("Por favor complete todos los campos requeridos: Client ID, Client Secret y Account ID."))

		# Actualizar el estado de conexión
		self.connection_status = "configured"

		# Forzar la actualización de los campos calculados
		self._compute_is_configured()
		self._compute_config_status()

		# Forzar actualización de la vista y recargar
		self.env.invalidate_all()

		return {
			"type": "ir.actions.act_window",
			"res_model": "zoom.config",
			"res_id": self.id,
			"view_mode": "form",
			"target": "current",
		}

	@api.model
	def get_config(self):
		"""Obtener configuración de Zoom"""
		config = self.search([], limit=1)
		if not config:
			config = self.create({})
		return config

	@api.model
	def get_active_config(self):
		"""Obtener configuración activa de Zoom"""
		config = self.search([("is_configured", "=", True)], limit=1)
		if not config:
			# Si no hay configuración activa, buscar cualquier configuración
			config = self.search([], limit=1)
		if not config:
			config = self.create({})
		return config

	def check_config_status(self):
		"""Verificar y actualizar el estado de la configuración"""
		self.ensure_one()

		# Verificar si tiene credenciales
		has_credentials = bool(
			self.client_id and
			self.client_secret and
			self.account_id
		)

		# Si no tiene credenciales, resetear todo
		if not has_credentials:
			self.write({
				"connection_status": "not_configured",
				"access_token": False,
				"refresh_token": False,
				"token_expires": False,
			})
		else:
			# Si tiene credenciales pero no está conectado, marcar como configurado
			if self.connection_status == "not_configured":
				self.connection_status = "configured"

			# Si hay token pero está expirado, intentar renovarlo
			if (self.access_token and self.token_expires and
					self.token_expires <= fields.Datetime.now() and
					self.connection_status == "connected"):
				try:
					self._get_access_token()
				except:
					self.connection_status = "error"

		# Forzar recálculo de campos computados
		self._compute_is_configured()
		self._compute_config_status()

		# Forzar actualización de la vista
		self.env.invalidate_all()

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Estado Verificado"),
				"message": _("Estado de configuración actualizado correctamente."),
				"type": "success",
				"sticky": False,
			}
		}

	def reset_config(self):
		"""Resetear la configuración a estado inicial"""
		self.ensure_one()

		self.write({
			"connection_status": "not_configured",
			"access_token": False,
			"refresh_token": False,
			"token_expires": False,
		})

		# Forzar recálculo de campos computados
		self._compute_is_configured()
		self._compute_config_status()

		return {
			"type": "ir.actions.client",
			"tag": "display_notification",
			"params": {
				"title": _("Configuración Reseteada"),
				"message": _("La configuración se ha reseteado al estado inicial."),
				"type": "info",
				"sticky": False,
			}
		}

	@api.model
	def create_default_config(self):
		"""Crear configuración por defecto"""
		existing_config = self.search([], limit=1)
		if not existing_config:
			self.create({
				"client_id": "",  # Debe ser configurado por el usuario
				"client_secret": "",  # Debe ser configurado por el usuario
				"account_id": "",  # Debe ser configurado por el usuario
				"webhook_secret": "",  # Opcional
				"base_url": "https://api.zoom.us/v2",
				"auto_record": False,
				"waiting_room": True,
				"join_before_host": False,
				"mute_on_entry": True,
			})
			_logger.info("Configuración por defecto de Zoom creada (credenciales vacías)")

	def test_connection(self):
		"""Probar conexión con Zoom API"""
		self.ensure_one()
		try:
			# Primero validar que los campos requeridos estén llenos
			if not self.client_id or not self.client_secret or not self.account_id:
				raise UserError(_("Por favor complete todos los campos requeridos: Client ID, Client Secret y Account ID."))

			# Actualizar el estado a 'configured' si no lo está
			if self.connection_status != "configured":
				self.connection_status = "configured"
				self._compute_is_configured()
				self._compute_config_status()

			# Si no hay token, obtener uno
			if not self.access_token or (self.token_expires and self.token_expires <= fields.Datetime.now()):
				self._get_access_token()

			# Probar conexión con API usando JWT
			headers = {
				"Authorization": f"Bearer {self.access_token}",
				"Content-Type": "application/json"
			}

			# Usar endpoint de lista de usuarios ya que no tenemos user:read:user:admin
			response = requests.get(
				f"{self.base_url}/users",
				headers=headers,
				timeout=10
			)

			if response.status_code == 200:
				self.connection_status = "connected"
				self._compute_config_status()

				# Sincronización automática después de configuración exitosa
				try:
					self._auto_sync_after_config()
				except Exception as sync_error:
					_logger.warning(f"Error en sincronización automática: {sync_error}")

				# Forzar actualización de la vista y recargar
				self.env.invalidate_all()

				return {
					"type": "ir.actions.act_window",
					"res_model": "zoom.config",
					"res_id": self.id,
					"view_mode": "form",
					"target": "current",
					"context": {"form_view_initial_mode": "readonly"},
				}
			else:
				self.connection_status = "error"
				self._compute_config_status()
				self.env.invalidate_all()
				raise UserError(_("❌ Error de conexión: %s") % response.text)

		except requests.exceptions.RequestException as e:
			self.connection_status = "error"
			self._compute_config_status()
			self.env.invalidate_all()
			raise UserError(_("❌ Error de conexión: %s") % str(e))
		except Exception as e:
			self.connection_status = "error"
			self._compute_config_status()
			self.env.invalidate_all()
			raise UserError(_("❌ Error inesperado: %s") % str(e))

	def _auto_sync_after_config(self):
		"""Sincronización automática después de configuración exitosa"""
		try:
			_logger.info("Iniciando sincronización automática después de configuración...")

			# Obtener token de acceso
			self._get_access_token()

			# Sincronizar reuniones desde Zoom
			import requests
			headers = {
				"Authorization": f"Bearer {self.access_token}",
				"Content-Type": "application/json"
			}

			# Obtener reuniones del usuario
			meetings_url = f"{self.base_url}/users/me/meetings"
			response = requests.get(meetings_url, headers=headers, timeout=30)

			if response.status_code == 200:
				meetings_data = response.json()
				meetings = meetings_data.get("meetings", [])

				synced_count = 0
				# Actualizar reuniones en Odoo
				for meeting_data in meetings:
					meeting_id = meeting_data.get("id")
					existing_meeting = self.env["zoom.meeting"].search([("zoom_meeting_id", "=", meeting_id)], limit=1)

					if not existing_meeting:
						# Convertir fecha de Zoom a formato Odoo
						start_time_str = meeting_data.get("start_time")
						if start_time_str:
							from datetime import datetime
							try:
								# Zoom devuelve fechas en formato ISO
								start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
								duration = meeting_data.get("duration", 60)

								# Crear reunión en Odoo
								self.env["zoom.meeting"].create({
									"name": meeting_data.get("topic", "Reunión Zoom"),
									"zoom_meeting_id": meeting_id,
									"start_time": start_time,
									"duration": duration,
									"join_url": meeting_data.get("join_url", ""),
									"password": meeting_data.get("password", ""),
									"status": "scheduled",
									"participants_count": meeting_data.get("participants_count", 0),
								})
								synced_count += 1
							except Exception as e:
								_logger.warning(f"Error creando reunión {meeting_id}: {e}")

				_logger.info(f"Sincronización automática completada: {synced_count} reuniones sincronizadas")

			else:
				_logger.warning(f"Error obteniendo reuniones: {response.status_code} - {response.text}")

		except Exception as e:
			_logger.error(f"Error en sincronización automática: {e}")
			raise

	def _get_access_token(self):
		"""Obtener token de acceso usando Server-to-Server OAuth de Zoom"""
		try:
			import base64

			import requests

			# Para Server-to-Server OAuth de Zoom
			# Crear credenciales en base64
			credentials = f"{self.client_id}:{self.client_secret}"
			encoded_credentials = base64.b64encode(credentials.encode()).decode()

			# Headers para la petición OAuth2
			headers = {
				"Authorization": f"Basic {encoded_credentials}",
				"Content-Type": "application/x-www-form-urlencoded"
			}

			# Datos para la petición Server-to-Server OAuth
			data = {
				"grant_type": "account_credentials",
				"account_id": self.account_id
			}

			# URL del endpoint de token de Zoom para Server-to-Server OAuth
			token_url = "https://zoom.us/oauth/token"

			# Hacer la petición
			response = requests.post(token_url, headers=headers, data=data, timeout=30)

			if response.status_code == 200:
				token_data = response.json()
				access_token = token_data.get("access_token")
				expires_in = token_data.get("expires_in", 3600)

				# Guardar el token y actualizar estado de conexión
				self.write({
					"access_token": access_token,
					"token_expires": fields.Datetime.now() + timedelta(seconds=expires_in),
					"connection_status": "connected"
				})
				_logger.info("Token Server-to-Server OAuth obtenido exitosamente para Zoom")
			else:
				_logger.error(f"Error obteniendo token Server-to-Server OAuth: {response.status_code} - {response.text}")
				raise UserError(_("Error obteniendo token Server-to-Server OAuth: %s") % response.text)

		except Exception as e:
			_logger.error(f"Error obteniendo token Server-to-Server OAuth: {str(e)}")
			raise UserError(_("Error obteniendo token Server-to-Server OAuth: %s") % str(e))

	@api.model
	def _sync_meetings_automatically(self):
		"""Sincronización automática de reuniones con Zoom"""
		try:
			config = self.get_active_config()
			if not config or not config.is_configured:
				_logger.info("Sincronización automática omitida: configuración no disponible")
				return

			# Obtener reuniones desde Zoom
			meetings = config.get_meetings_from_zoom()
			if not meetings:
				_logger.info("Sincronización automática: no se encontraron reuniones en Zoom")
				return

			# Crear o actualizar reuniones en Odoo
			synced_count = 0
			for meeting_data in meetings:
				# Convertir fecha de Zoom a formato Odoo
				start_time_str = meeting_data.get("start_time")
				start_time = None
				if start_time_str:
					try:
						from datetime import datetime
						# Convertir de ISO 8601 a formato Odoo (naive datetime)
						start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00")).replace(tzinfo=None)
					except Exception as e:
						_logger.warning(f"Error convirtiendo fecha {start_time_str}: {e}")

				existing_meeting = self.env["zoom.meeting"].search([
					("meeting_id", "=", meeting_data.get("id"))
				], limit=1)

				if existing_meeting:
					# Actualizar reunión existente
					existing_meeting.write({
						"name": meeting_data.get("topic", ""),
						"start_time": start_time,
						"duration": meeting_data.get("duration", 0),
						"join_url": meeting_data.get("join_url", ""),
						"start_url": meeting_data.get("start_url", ""),
						"status": meeting_data.get("status", "scheduled"),
					})
				else:
					# Crear nueva reunión
					self.env["zoom.meeting"].create({
						"name": meeting_data.get("topic", ""),
						"meeting_id": meeting_data.get("id"),
						"start_time": start_time,
						"duration": meeting_data.get("duration", 0),
						"join_url": meeting_data.get("join_url", ""),
						"start_url": meeting_data.get("start_url", ""),
						"status": meeting_data.get("status", "scheduled"),
					})
				synced_count += 1

			_logger.info(f"Sincronización automática completada: {synced_count} reuniones procesadas")

		except Exception as e:
			_logger.error(f"Error en sincronización automática: {str(e)}")
			# No lanzar excepción para evitar que falle el cron job

	def sync_meetings_manually(self):
		"""Sincronizar reuniones manualmente sin webhooks"""
		try:
			if not self.use_webhooks:
				# Obtener token de acceso
				self._get_access_token()

				# Sincronizar reuniones desde Zoom
				import requests
				headers = {
					"Authorization": f"Bearer {self.access_token}",
					"Content-Type": "application/json"
				}

				# Obtener reuniones del usuario
				meetings_url = f"{self.base_url}/users/me/meetings"
				response = requests.get(meetings_url, headers=headers, timeout=30)

				if response.status_code == 200:
					meetings_data = response.json()
					meetings = meetings_data.get("meetings", [])

					# Actualizar reuniones en Odoo
					for meeting_data in meetings:
						meeting_id = meeting_data.get("id")
						existing_meeting = self.env["zoom.meeting"].search([("zoom_meeting_id", "=", meeting_id)], limit=1)

						if not existing_meeting:
							# Convertir fecha de Zoom a formato Odoo
							start_time_str = meeting_data.get("start_time")
							start_time = None
							if start_time_str:
								try:
									from datetime import datetime
									# Convertir de ISO 8601 a formato Odoo (naive datetime)
									start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00")).replace(tzinfo=None)
								except Exception as e:
									_logger.warning(f"Error convirtiendo fecha {start_time_str}: {e}")

							# Crear nueva reunión
							meeting = self.env["zoom.meeting"].create({
								"name": meeting_data.get("topic", "Reunión Zoom"),
								"meeting_id": meeting_id,
								"start_time": start_time,
								"duration": meeting_data.get("duration", 60),
								"join_url": meeting_data.get("join_url"),
								"status": "scheduled",
								"zoom_created": True
							})

							# Crear evento en calendario automáticamente
							meeting._create_calendar_event()

					_logger.info(f"Sincronizadas {len(meetings)} reuniones desde Zoom")
					return {
						"type": "ir.actions.client",
						"tag": "display_notification",
						"params": {
							"title": "Sincronización Exitosa",
							"message": f"Se sincronizaron {len(meetings)} reuniones desde Zoom",
							"type": "success",
						}
					}
				else:
					_logger.error(f"Error sincronizando reuniones: {response.status_code} - {response.text}")
					raise UserError(_("Error sincronizando reuniones: %s") % response.text)
			else:
				raise UserError(_("Los webhooks están activados. La sincronización manual no es necesaria."))

		except Exception as e:
			_logger.error(f"Error en sincronización manual: {str(e)}")
			raise UserError(_("Error en sincronización manual: %s") % str(e))

	def get_meetings_from_zoom(self):
		"""Obtener reuniones desde Zoom API"""
		try:
			# Obtener token si es necesario
			if not self.access_token or (self.token_expires and self.token_expires <= fields.Datetime.now()):
				self._get_access_token()

			if not self.access_token:
				raise UserError(_("No se pudo obtener el token de acceso"))

			headers = {
				"Authorization": f"Bearer {self.access_token}",
				"Content-Type": "application/json"
			}

			# Obtener reuniones del usuario
			response = requests.get(
				f"{self.base_url}/users/me/meetings",
				headers=headers,
				timeout=30
			)

			if response.status_code == 200:
				data = response.json()
				meetings = data.get("meetings", [])
				_logger.info(f"Obtenidas {len(meetings)} reuniones desde Zoom")
				return meetings
			else:
				_logger.error(f"Error obteniendo reuniones: {response.status_code} - {response.text}")
				raise UserError(_("Error obteniendo reuniones: %s") % response.text)

		except Exception as e:
			_logger.error(f"Error obteniendo reuniones desde Zoom: {str(e)}")
			raise UserError(_("Error obteniendo reuniones desde Zoom: %s") % str(e))

	def sync_meetings_automatically(self):
		"""Sincronización automática de reuniones desde Zoom a Odoo"""
		try:
			_logger.info("Iniciando sincronización automática de reuniones...")

			# Obtener reuniones desde Zoom
			zoom_meetings = self.get_meetings_from_zoom()

			if not zoom_meetings:
				_logger.info("No hay reuniones en Zoom para sincronizar")
				return

			# Obtener reuniones existentes en Odoo
			existing_meetings = self.env["zoom.meeting"].search([])
			existing_zoom_ids = set(existing_meetings.mapped("meeting_id"))

			created_count = 0
			updated_count = 0

			for meeting_data in zoom_meetings:
				zoom_id = str(meeting_data.get("id"))
				topic = meeting_data.get("topic", "Sin título")
				start_time = meeting_data.get("start_time")
				duration = meeting_data.get("duration", 0)
				join_url = meeting_data.get("join_url", "")
				status = meeting_data.get("status", "scheduled")

				# Convertir fecha de Zoom a formato Odoo
				if start_time:
					try:
						from datetime import datetime
						odoo_date = datetime.fromisoformat(start_time.replace("Z", "+00:00")).replace(tzinfo=None)
					except:
						odoo_date = fields.Datetime.now()
				else:
					odoo_date = fields.Datetime.now()

				# Determinar estado de control total del equipo
				control_status = self._get_control_status(status, start_time)

				if zoom_id in existing_zoom_ids:
					# Actualizar reunión existente
					existing_meeting = existing_meetings.filtered(lambda m: m.meeting_id == zoom_id)
					if existing_meeting:
						existing_meeting.write({
							"name": topic,
							"start_time": odoo_date,
							"duration": duration,
							"join_url": join_url,
							"status": "active" if status == "started" else "scheduled",
							"last_sync": fields.Datetime.now(),
						})
						updated_count += 1
				else:
					# Crear nueva reunión
					self.env["zoom.meeting"].create({
						"name": topic,
						"meeting_id": zoom_id,
						"start_time": odoo_date,
						"duration": duration,
						"join_url": join_url,
						"status": "active" if status == "started" else "scheduled",
						"zoom_created": True,
						"expected_participants": 1,
						"actual_participants": 0,
						"last_sync": fields.Datetime.now(),
					})
					created_count += 1

			_logger.info(f"Sincronización completada: {created_count} creadas, {updated_count} actualizadas")

			return {
				"created": created_count,
				"updated": updated_count,
				"total": len(zoom_meetings)
			}

		except Exception as e:
			_logger.error(f"Error en sincronización automática: {str(e)}")
			raise UserError(_("Error en sincronización automática: %s") % str(e))

	def _get_control_status(self, status, start_time):
		"""Determinar el estado de control total del equipo"""

		if status == "started":
			return "Activo"
		elif status == "finished":
			return "Finalizado"
		elif status == "cancelled":
			return "Cancelado"
		elif start_time:
			try:
				meeting_time = datetime.fromisoformat(start_time.replace("Z", "+00:00")).replace(tzinfo=None)
				now = datetime.now()
				if meeting_time > now:
					return "Programado"
				else:
					return "Finalizado"
			except:
				return "Programado"
		else:
			return "Programado"

	def create_zoom_meeting(self, meeting_data):
		"""Crear reunión en Zoom API desde configuración"""
		try:
			# Obtener token si es necesario
			if not self.access_token or (self.token_expires and self.token_expires <= fields.Datetime.now()):
				self._get_access_token()

			headers = {
				"Authorization": f"Bearer {self.access_token}",
				"Content-Type": "application/json"
			}

			# Preparar datos para Zoom API
			zoom_data = {
				"topic": meeting_data.get("name", "Reunión Odoo"),
				"type": 2,  # Reunión programada
				"start_time": meeting_data.get("start_time", fields.Datetime.now().isoformat()),
				"duration": meeting_data.get("duration", 60),
				"timezone": "America/Lima",
				"settings": {
					"host_video": True,
					"participant_video": True,
					"join_before_host": self.join_before_host,
					"mute_upon_entry": self.mute_on_entry,
					"waiting_room": self.waiting_room,
					"auto_recording": "local" if self.auto_record else "none",
				}
			}

			response = requests.post(
				f"{self.base_url}/users/me/meetings",
				headers=headers,
				json=zoom_data,
				timeout=30
			)

			if response.status_code == 201:
				meeting_info = response.json()
				return {
					"id": str(meeting_info.get("id")),
					"join_url": meeting_info.get("join_url"),
					"start_url": meeting_info.get("start_url"),
					"zoom_created": True,
					"last_sync": fields.Datetime.now()
				}
			else:
				_logger.error(f"Error creando reunión en Zoom: {response.text}")
				raise UserError(_("Error al crear reunión en Zoom: %s") % response.text)

		except requests.exceptions.RequestException as e:
			_logger.error(f"Error de conexión con Zoom: {str(e)}")
			raise UserError(_("Error de conexión con Zoom: %s") % str(e))
		except Exception as e:
			_logger.error(f"Error inesperado: {str(e)}")
			raise UserError(_("Error inesperado: %s") % str(e))
