from params import PI_BASE_URL
from views import *

from flask import abort, send_from_directory


def load_routes(app, actions):

    @app.route('/radiodns/epg/XSI.xml')
    @app.cache.cached(timeout=3600)
    def epg_xml():
        """Special call for EPG xml"""

        from models import Station, Channel, GenericServiceFollowingEntry, Ecc
        from flask import render_template, Response
        
        stations = Station.query.all()
                
        import datetime

        time_format = '%Y-%m-%dT%H:%M:%S%z'

        list = []

        for elem in stations:
            
            entries = []
 
            # Channels
            for elem2 in elem.channels.order_by(Channel.name).all():
                
                if elem2.servicefollowingentry.active:
                    entries.append(elem2.servicefollowingentry.json)
  
                    if elem2.type_id == 'fm':  # For FM, also add with the country code
                        try:
                            data2 = elem2.servicefollowingentry.json
  
                            # Split the URI
                            uri_dp = data2['uri'].split(':', 2)
                            uri_p = uri_dp[1].split('.')
  
                            pi_code = uri_p[0]
  
                            # Get the ISO code form the picode
                            ecc = Ecc.query.filter_by(pi=pi_code[0].upper(), ecc=pi_code[1:].upper()).first()
  
                            uri_p[0] = ecc.iso.lower()
  
                            # Update the new URL
                            data2['uri'] = uri_dp[0] + ':' + '.'.join(uri_p)
                            
                            # Add the service
                            entries.append(data2)
  
                        except:
                            #pass
                            app.logger.error('Exception in epg_xml')
 
            # Custom entries
            for elem2 in elem.servicefollowingentries.order_by(GenericServiceFollowingEntry.channel_uri).all():
                if elem2.active:
                    try:
                        entries.append(elem2.json)
                    except:
                        app.logger.error('Exception 2 in epg_xml')
 
            if entries:
                list.append([elem.json, entries])
        
        return Response(render_template('radioepg/servicefollowing/xml.html', stations=list, creation_time=datetime.datetime.now().strftime(time_format)), mimetype='text/xml')

    @app.route('/radiodns/logo/<int:id>/<int:w>/<int:h>/logo.png')
    def logo(id, w, h):
        """Return a logo for a station"""

        from models import Station
        import os

        station = Station.query.filter(Station.id == id).first()

        if not station:
            abort(404)

        dest_file = 'media/uploads/radioepg/cache/S%s_W%s_H%s_L%s.png' % (str(int(id)), str(int(w)), str(int(h)), str(station.epg_picture_id) if station.epg_picture_id else 'B')

        if not os.path.isfile(dest_file):

            from PIL import Image
            size = (w, h)
            image = Image.open(station.epg_picture.filename if station.epg_picture else 'media/uploads/radioepg/default.png')
            image.thumbnail(size, Image.ANTIALIAS)
            background = Image.new('RGBA' if station.epg_picture else 'RGB', size, (255, 255, 255, 0))
            background.paste(image, ((size[0] - image.size[0]) / 2, (size[1] - image.size[1]) / 2))

            background.save(dest_file)

        return send_from_directory(".", dest_file)

    @app.route('/radiodns/epg/<path:path>/<int:date>_PI.xml')
    def epg_sch_xml(path, date):
        """Special call for EPG scheduling xml"""

        from models import Channel
        from flask import render_template, Response
        
        base_type = path.split('/')[0]
        topiced_path = '/topic/' + path

        station = None

        for channel in Channel.query.filter(Channel.type_id == base_type).all():
            if channel.topic_no_slash == topiced_path:
                station = channel.station

        if station:

            import datetime

            time_format = '%Y-%m-%dT%H:%M:%S%z'

            today = datetime.date.today()
            start_date = datetime.datetime.combine(today - datetime.timedelta(days=today.weekday()), datetime.time())
            end_date = start_date + datetime.timedelta(days=6, hours=23, minutes=59, seconds=59)

            # Filter by date
            date_to_filter = datetime.datetime.strptime(str(date), "%Y%m%d").date()
            real_start_date = datetime.datetime.combine(date_to_filter, datetime.time())
            real_end_date = start_date + datetime.timedelta(days=6, hours=23, minutes=59, seconds=59)

            list = []

            for elem in station.schedules.all():
                elem.start_date = start_date

                if elem.date_of_start_time.date() == date_to_filter:
                    list.append(elem.json)

            return Response(render_template('radioepg/schedule/xml.html', schedules=list, start_time=real_start_date.strftime(time_format), end_time=real_end_date.strftime(time_format), creation_time=datetime.datetime.now().strftime(time_format)), mimetype='text/xml')

        abort(404)
        # return 'Station not found'

    @app.route(PI_BASE_URL + "ping")
    def ping():
        """The ping method: Just return the data provided"""

        if not check_ip(request):
            return

        return jsonify(data=request.args.get('data', ''))

    @app.route(PI_BASE_URL + "version")
    def version():
        """The version method: Return current information about the version"""
        return jsonify(result='Ok', version=PI_API_VERSION, protocol=PI_API_NAME)

    @app.route(PI_BASE_URL + "mail", methods=['POST'])
    def mail():
        """The mail method: Process mail handling"""

        data = request.form['response_id'].split(':')

        if data[0] == 'dis':

            discussion = Discussion.query.filter(Discussion.id == int(data[1])).first()
            if discussion.is_closed:
                api.send_mail('', 'Error', [api.get_user(data[2]).email], 'You tried to reply to the discussion ' + discussion.title + ' but the discussion is closed.\n\nBests,')

                return jsonify(result='Ok')

            post = DiscussionPost()
            post.discussion_id = int(data[1])
            post.author = int(data[2])
            post.date = datetime.now()
            post.message = request.form['message']

            db.session.add(post)
            db.session.commit()

            post.send_mail()

        return jsonify(result='Ok')

    # Register the 3 URLs (meta, template, action) for each actions
    # We test for each element in the module actions if it's an action
    # (added by the decorator in utils)
    for act in dir(actions):
        obj = getattr(actions, act)
        if hasattr(obj, 'pi_api_action') and obj.pi_api_action:
            # We found an action and we can now add it to our routes

            # Meta
            app.add_url_rule(
                PI_BASE_URL + 'meta' + obj.pi_api_route,
                view_func=MetaView.as_view('meta_' + act, action=obj))

            # Template
            app.add_url_rule(
                PI_BASE_URL + 'template' + obj.pi_api_route,
                view_func=TemplateView.as_view('template_' + act, action=obj))

            # Action
            app.add_url_rule(
                PI_BASE_URL + 'action' + obj.pi_api_route,
                view_func=ActionView.as_view('action_' + act, action=obj),
                methods=obj.pi_api_methods)
