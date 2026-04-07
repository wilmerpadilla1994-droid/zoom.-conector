Zoom Integration for Odoo
==========================

This module provides seamless integration between Zoom and Odoo, allowing you to create, manage, and synchronize Zoom meetings directly from your Odoo instance.

Features
--------

* **Meeting Management**: Create, start, and manage Zoom meetings from Odoo
* **Automatic Synchronization**: Keep your meetings synchronized between Odoo and Zoom
* **Dashboard**: Customizable dashboard for meeting overview and management
* **Helpdesk Integration**: Integrate Zoom meetings with helpdesk tickets
* **Calendar Integration**: Sync meetings with Odoo calendar
* **Attendee Management**: Manage meeting participants and track attendance
* **Webhook Support**: Real-time updates via Zoom webhooks
* **Security**: Encrypted API credentials and secure communication

Requirements
------------

* Odoo 18.0 or higher
* Zoom Pro account or higher
* Server-to-Server OAuth app in Zoom Marketplace
* Base, Mail, Calendar, Helpdesk modules

Installation
------------

1. Copy the module to your Odoo addons directory
2. Update your addons list in Odoo
3. Install the module from the Apps menu

Configuration
-------------

Step 1: Obtain Zoom API Credentials
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Log in to your Zoom account at https://marketplace.zoom.us/
2. Go to "Develop" > "Build App"
3. Choose "Server-to-Server OAuth" app type
4. Enter app information and create the app
5. Copy the following credentials:
   - Account ID (found in your app credentials)
   - Client ID (API Key)
   - Client Secret (API Secret)

Step 2: Configure Zoom App Permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. In your Zoom app dashboard, go to "Scopes"
2. Add the following scopes:
   - `meeting:write` - Create and manage meetings
   - `meeting:read` - Read meeting information
   - `user:read` - Read user information
   - `recording:read` - Access recordings (optional)

Step 3: Configure in Odoo
~~~~~~~~~~~~~~~~~~~~~~~~~

1. Navigate to **Settings > Zoom Configuration**
2. Enter your Zoom API credentials:
   - **Account ID**: Your Zoom account ID
   - **Client ID (API Key)**: Your app's Client ID
   - **Client Secret (API Secret)**: Your app's Client Secret
   - **Webhook Secret**: Optional, for webhook integration
3. **Enable Webhooks** (optional):
   - Only enable if you have a public domain configured
   - Set up webhook endpoint in your Zoom app
   - Add webhook secret for validation
4. Click **Test Connection** to verify credentials
5. Save your configuration

Step 4: Verify Integration
~~~~~~~~~~~~~~~~~~~~~~~~~

1. Navigate to **Zoom > Zoom Meetings**
2. Click "Create" to test meeting creation
3. Verify the meeting appears in your Zoom account
4. Test joining the meeting with the generated link

Usage
-----

Creating Meetings
~~~~~~~~~~~~~~~~~

1. Navigate to **Zoom > Zoom Meetings**
2. Click **Create** button
3. Fill in meeting details:
   - **Topic**: Meeting title/subject
   - **Start Time**: Schedule the meeting
   - **Duration**: Meeting length in minutes
   - **Password**: Optional meeting password
   - **Waiting Room**: Enable/disable waiting room
   - **Auto Recording**: Enable automatic recording
4. Add participants in the **Attendees** tab
5. Click **Save** to create the meeting
6. Click **Start Meeting** to begin the session

Helpdesk Integration
~~~~~~~~~~~~~~~~~~~~

1. Open a helpdesk ticket from **Helpdesk > Tickets**
2. In the ticket form, click **Create Zoom Meeting**
3. Configure meeting settings (same as regular meetings)
4. The meeting link will be automatically added to the ticket description
5. Participants can join directly from the ticket

Calendar Integration
~~~~~~~~~~~~~~~~~~~~~

1. Go to **Calendar** and create a new event
2. Click **Add Zoom Meeting** button
3. Meeting details will be automatically added to the event
4. Save the calendar event
5. Meeting link appears in event description

Dashboard Features
~~~~~~~~~~~~~~~~~~

- **Upcoming Meetings**: View all scheduled meetings
- **Meeting Statistics**: Track total meetings, participants, duration
- **Quick Actions**: Start meetings, create new meetings
- **Recent Activity**: Monitor meeting status changes

Managing Attendees
~~~~~~~~~~~~~~~~~

1. Open any meeting from **Zoom > Zoom Meetings**
2. Go to **Attendees** tab
3. Click **Add Attendee** to invite participants
4. Track attendance status:
   - **Invited**: Participant invited but not joined
   - **Joined**: Participant has joined the meeting
   - **Left**: Participant has left the meeting

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

"Invalid API Credentials" Error
    - Verify Account ID, Client ID, and Client Secret are correct
    - Ensure your Zoom app is activated in the marketplace
    - Check that required scopes are added to your app

"Meeting Not Created" Error
    - Verify your Zoom account has meeting creation permissions
    - Check if you've exceeded your Zoom plan limits
    - Ensure the meeting start time is in the future

"Webhook Not Working"
    - Verify your domain is publicly accessible
    - Check webhook secret matches in both Odoo and Zoom
    - Ensure webhook events are enabled in your Zoom app

"Cannot Join Meeting"
    - Check if meeting is started (not just scheduled)
    - Verify participant has proper permissions
    - Ensure meeting password is correct if enabled

Debug Mode
~~~~~~~~~~

Enable debug logging to troubleshoot issues:
1. Go to **Settings > Technical > Logging**
2. Enable logging for `zoom_connector` module
3. Check log files for detailed error messages

Security
--------

* All API credentials are encrypted in the database
* Webhook validation ensures secure communication
* Role-based access control for meeting management

Support
-------

For technical support and inquiries, please contact our support team.

License
-------

This module is licensed under AGPL-3. See LICENSE file for details.

Version History
---------------

* **18.0.1.0.0**: Initial release with full Zoom integration
