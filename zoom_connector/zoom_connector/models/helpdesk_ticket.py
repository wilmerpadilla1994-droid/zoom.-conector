# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    control_total = fields.Boolean(
        string='Control Total',
        help='Indica si se realizó control total de la máquina durante la atención.'
    )

    zoom_meeting_ids = fields.One2many(
        'zoom.meeting',
        'ticket_id',
        string='Reuniones Zoom',
        help='Reuniones de Zoom asociadas a este ticket'
    )

    zoom_meeting_count = fields.Integer(
        string='Cantidad de Reuniones',
        compute='_compute_zoom_meeting_count',
        help='Número total de reuniones Zoom asociadas'
    )

    active_zoom_meeting = fields.Many2one(
        'zoom.meeting',
        string='Reunión Activa',
        compute='_compute_active_zoom_meeting',
        help='Reunión Zoom activa o próxima'
    )

    @api.depends('zoom_meeting_ids')
    def _compute_zoom_meeting_count(self):
        for ticket in self:
            ticket.zoom_meeting_count = len(ticket.zoom_meeting_ids)

    @api.depends('zoom_meeting_ids', 'zoom_meeting_ids.status', 'zoom_meeting_ids.start_time')
    def _compute_active_zoom_meeting(self):
        for ticket in self:
            active_meeting = ticket.zoom_meeting_ids.filtered(
                lambda m: m.status in ['scheduled', 'active']
            ).sorted('start_time')
            ticket.active_zoom_meeting = active_meeting[0] if active_meeting else False

    def action_create_zoom_meeting(self):
        """Crear reunión Zoom programada para el ticket"""
        self.ensure_one()

        meeting = self.env['zoom.meeting'].create({
            'name': f'Reunión - {self.name}',
            'start_time': fields.Datetime.now() + timedelta(hours=1),
            'duration': 60,
            'ticket_id': self.id,
            'status': 'scheduled',
        })

        try:
            meeting_data = {
                'name': meeting.name,
                'start_time': meeting.start_time.isoformat(),
                'duration': meeting.duration,
            }
            zoom_result = meeting.create_zoom_meeting(meeting_data)
            meeting.write(zoom_result)
            meeting._create_calendar_event()

            return {
                'type': 'ir.actions.act_window',
                'name': _('Reunión Zoom Creada'),
                'res_model': 'zoom.meeting',
                'res_id': meeting.id,
                'view_mode': 'form',
                'target': 'new',
            }
        except Exception as e:
            _logger.error(f'Error creando reunión Zoom: {str(e)}')
            raise UserError(_('Error al crear reunión en Zoom: %s') % str(e))

    def action_start_instant_zoom(self):
        """Iniciar reunión Zoom instantánea para el ticket"""
        self.ensure_one()

        meeting = self.env['zoom.meeting'].create({
            'name': f'Reunión Instantánea - {self.name}',
            'start_time': fields.Datetime.now(),
            'duration': 60,
            'ticket_id': self.id,
            'status': 'scheduled',
        })

        try:
            return meeting.create_instant_meeting()
        except Exception as e:
            _logger.error(f'Error iniciando reunión instantánea: {str(e)}')
            raise UserError(_('Error al iniciar reunión instantánea: %s') % str(e))

    def action_join_zoom_meeting(self):
        """Unirse a reunión Zoom activa/actual del ticket"""
        self.ensure_one()
        if not self.active_zoom_meeting:
            raise UserError(_('No hay reuniones Zoom activas para este ticket'))
        return self.active_zoom_meeting.action_join_meeting()

    def action_view_zoom_meetings(self):
        """Ver reuniones Zoom asociadas al ticket"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reuniones Zoom'),
            'res_model': 'zoom.meeting',
            'view_mode': 'list,form',
            'domain': [('ticket_id', '=', self.id)],
            'context': {'default_ticket_id': self.id},
            'target': 'current',
        }
