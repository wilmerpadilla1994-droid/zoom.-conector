{
	"name": "Zoom Integration",
	"version": "18.0.1.0.0",
	"category": "Productivity",
	"summary": "Integración de Zoom con Odoo",
	"description": """
        Módulo de integración de Zoom para Odoo
        =============================================

        Funcionalidades:
        - Crear, iniciar y gestionar reuniones de Zoom desde Odoo
        - Sincronización automática de reuniones
        - Control total del equipo automático
        - Dashboard personalizado
        - Integración con Helpdesk (tickets)
    """,
	"author": "Tecserca",
	"website": "https://www.linkedin.com/in/wpadilla/",
	"price": ,
	"currency": "EUR",
	"depends": [
		"base",
		"mail",
		"helpdesk",
		"calendar",
		"web",
	],
	"data": [
		"security/ir.model.access.csv",
		"static/src/assets.xml",
		"views/zoom_meeting_views.xml",
		"views/zoom_meeting_attendee_views.xml",
		"views/zoom_dashboard_views.xml",
		"views/zoom_config_views.xml",
		"views/helpdesk_ticket_views.xml",
		"views/calendar_event_views.xml",
		"data/zoom_data.xml",
		"data/email_templates.xml",
		"data/cron_jobs.xml",
	],
	"demo": [],
	"installable": True,
	"auto_install": False,
	"application": True,
	"license": "LGPL-3",
	"images": [
		"static/description/Captura desde 2025-09-14 01-30-27.png",
		"static/description/Captura desde 2025-09-14 01-31-03.png",
		"static/description/Captura desde 2025-09-14 01-31-13.png",
		"static/description/Captura desde 2025-09-14 01-31-30.png",
		"static/description/Captura desde 2025-09-14 01-31-39.png",
		"static/description/Captura desde 2025-09-14 01-32-08.png",
		"static/description/Captura desde 2025-09-14 01-32-53.png",
		"static/description/Captura desde 2025-09-14 01-33-21.png",
		"static/description/Captura desde 2025-09-14 01-33-54.png"
	],
}
