from http.client import responses

from django.urls import reverse
from django.shortcuts import render
from django.http import HttpResponse, HttpRequest
from django.views import View
from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from urllib.parse import unquote
import gzip
import os
import re

from django.shortcuts import render

from bookmarks.models import Bookmark, BookmarkAsset


class WebDAVMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.method.lower() in ['propfind', 'proppatch', 'mkcol', 'copy', 'move', 'lock', 'unlock', 'options', 'get']:
            response['DAV'] = '1'  # Indicate WebDAV compliance
            # response['DAV'] = '1, 2'  # Indicate WebDAV compliance
            response['Allow'] = ', '.join([
                'OPTIONS', 'GET', 'HEAD',
                # 'POST', 'PUT', 'DELETE',
                'PROPFIND',
                # 'PROPPATCH', 'MKCOL', 'COPY', 'MOVE', 'LOCK', 'UNLOCK'
            ])
        return response


@method_decorator(csrf_exempt, name='dispatch')
class WebDAVView(View):
    def dispatch(self, request, *args, **kwargs):
        method = request.method.lower()

        # Handle standard methods
        if method in self.http_method_names:
            return super().dispatch(request, *args, **kwargs)

        # Handle WebDAV methods
        if hasattr(self, method):
            handler = getattr(self, method)
            return handler(request, *args, **kwargs)

        return HttpResponse(status=405)  # Method Not Allowed

    def options(self, request, *args, **kwargs):
        return HttpResponse(
            status=204,
            # headers={
            #     "Allow": "OPTIONS,PROPFIND,GET",
            #     # "Allow": "OPTIONS,PROPFIND,GET,PUT,LOCK,UNLOCK,DELETE,MKCOL,MOVE",
            #     "DAV": "1,2"
            # }
        )

    def propfind(self, request, tab, path, *args, **kwargs):
        return HttpResponse(status=501)  # Not Implemented by default

    def proppatch(self, request, *args, **kwargs):
        return HttpResponse(status=501)

    def mkcol(self, request, *args, **kwargs):
        return HttpResponse(status=501)

    def copy(self, request, *args, **kwargs):
        return HttpResponse(status=501)

    def move(self, request, *args, **kwargs):
        return HttpResponse(status=501)

    def lock(self, request, *args, **kwargs):
        return HttpResponse(status=501)

    def unlock(self, request, *args, **kwargs):
        return HttpResponse(status=501)

    def report(self, request, *args, **kwargs):
        return HttpResponse(status=501)


def path_parts(path):
    path = unquote(path)  # Decode URL-encoded characters

    if not path:  # Root collection
        folder_path = '/'
        resource_name = ''
    else:
        parts = path.rstrip('/').split('/')
        if len(parts) == 1:
            folder_path = '/'
            resource_name = parts[0]
        else:
            folder_path = '/' + '/'.join(parts[:-1]) + '/'
            resource_name = parts[-1]

    return folder_path, resource_name


def _get_asset_content(asset):
    filepath = os.path.join(settings.LD_ASSET_FOLDER, asset.file)

    if not os.path.exists(filepath):
        # todo update 404
        raise "404"

    if asset.gzip:
        with gzip.open(filepath, "rb") as f:
            content = f.read()
    else:
        with open(filepath, "rb") as f:
            content = f.read()

    return content


def _parse_ref(ref):
    # parse my own encoded naming scheme
    # generated in _bookmark_to_response
    return int(ref.split('.html')[0].split('-')[-1])


def _bookmark_to_response(bookmark):
    return """
        <D:response>
            <D:href>/webdav/{}-{}.html</D:href>
            <D:propstat>
                <D:prop>
                    <p:resourcetype/>
                    <p:creationdate>2025-06-21T14:21:41Z</p:creationdate>
                    <p:getcontentlength>0</p:getcontentlength>
                    <p:getlastmodified>Sat, 21 Jun 2025 14:21:41 GMT</p:getlastmodified>
                    <p:getetag>"0-63815b28fcd8a"</p:getetag>
                    <p:executable>F</p:executable>
                    <D:supportedlock></D:supportedlock>
                    <D:getcontenttype>application/rss+xml</D:getcontenttype>
                </D:prop>
                <D:status>HTTP/1.1 200 OK</D:status>
            </D:propstat>
        </D:response>
    """.format(
        # bookmark.title,
        re.sub('[^0-9a-zA-Z]+', '-', bookmark.title),
        bookmark.id
    )


class MyWebDAVResource(WebDAVView):
    def propfind(self, request, path, *args, **kwargs):
        folder, file = path_parts(path)
        folder = '/webdav' + folder

        # Implement PROPFIND response
        if request.get_full_path() == '/webdav/all/':
            bookmarks = Bookmark.objects.exclude(latest_snapshot_body_id__isnull=True)
            print(bookmarks)
            responses = [_bookmark_to_response(b) for b in bookmarks]

            return HttpResponse(
                """<?xml version="1.0" encoding="utf-8" ?>
                <D:multistatus xmlns:D="DAV:" xmlns:p="http://apache.org/dav/props/">
                    <D:response>
                        <D:href>/webdav/all/</D:href>
                        <D:propstat>
                            <D:prop>
                                <p:resourcetype>
                                    <D:collection/>
                                </p:resourcetype>
                                <p:creationdate>2025-06-21T20:34:35Z</p:creationdate>
                                <p:getlastmodified>Sat, 21 Jun 2025 20:34:35 GMT</p:getlastmodified>
                                <p:getetag>"e0-6381ae82aeb33"</p:getetag>
                                <D:supportedlock></D:supportedlock>
                                <D:getcontenttype>httpd/unix-directory</D:getcontenttype>
                            </D:prop>
                            <D:status>HTTP/1.1 200 OK</D:status>
                        </D:propstat>
                    </D:response>
                    {}
                </D:multistatus>
                """.format('\n'.join(responses)),
                content_type='application/xml; charset="utf-8"',
                status=207
            )

        elif request.get_full_path() == '/webdav/unread/':
            bookmarks = Bookmark.objects.filter(unread=True, latest_snapshot_body_id__isnull=False)
            print(bookmarks)
            responses = [_bookmark_to_response(b) for b in bookmarks]

            return HttpResponse(
                """<?xml version="1.0" encoding="utf-8" ?>
                <D:multistatus xmlns:D="DAV:" xmlns:p="http://apache.org/dav/props/">
                    <D:response>
                        <D:href>/webdav/unread/</D:href>
                        <D:propstat>
                            <D:prop>
                                <p:resourcetype>
                                    <D:collection/>
                                </p:resourcetype>
                                <p:creationdate>2025-06-21T20:34:35Z</p:creationdate>
                                <p:getlastmodified>Sat, 21 Jun 2025 20:34:35 GMT</p:getlastmodified>
                                <p:getetag>"e0-6381ae82aeb33"</p:getetag>
                                <D:supportedlock></D:supportedlock>
                                <D:getcontenttype>httpd/unix-directory</D:getcontenttype>
                            </D:prop>
                            <D:status>HTTP/1.1 200 OK</D:status>
                        </D:propstat>
                    </D:response>
                    {}
                </D:multistatus>
                """.format('\n'.join(responses)),
                content_type='application/xml; charset="utf-8"',
                status=207
            )

        elif request.get_full_path() == '/webdav/':
            return HttpResponse(
                """<?xml version="1.0" encoding="utf-8" ?>
                <D:multistatus xmlns:D="DAV:" xmlns:p="http://apache.org/dav/props/">
                    <D:response>
                        <D:href>/webdav/</D:href>
                        <D:propstat>
                            <D:prop>
                                <p:resourcetype>
                                    <D:collection/>
                                </p:resourcetype>
                                <p:creationdate>2025-06-21T20:34:35Z</p:creationdate>
                                <p:getlastmodified>Sat, 21 Jun 2025 20:34:35 GMT</p:getlastmodified>
                                <p:getetag>"e0-6381ae82aeb33"</p:getetag>
                                <D:supportedlock></D:supportedlock>
                                <D:getcontenttype>httpd/unix-directory</D:getcontenttype>
                            </D:prop>
                            <D:status>HTTP/1.1 200 OK</D:status>
                        </D:propstat>
                    </D:response>
                    
                    <D:response>
                        <D:href>/webdav/all/</D:href>
                        <D:propstat>
                            <D:prop>
                                <p:resourcetype>
                                    <D:collection/>
                                </p:resourcetype>
                                <p:creationdate>2025-06-21T20:34:35Z</p:creationdate>
                                <p:getlastmodified>Sat, 21 Jun 2025 20:34:35 GMT</p:getlastmodified>
                                <p:getetag>"e0-6381ae82aeb34"</p:getetag>
                                <D:supportedlock></D:supportedlock>
                                <D:getcontenttype>httpd/unix-directory</D:getcontenttype>
                            </D:prop>
                            <D:status>HTTP/1.1 200 OK</D:status>
                        </D:propstat>
                    </D:response>
                    
                    <D:response>
                        <D:href>/webdav/unread/</D:href>
                        <D:propstat>
                            <D:prop>
                                <p:resourcetype>
                                    <D:collection/>
                                </p:resourcetype>
                                <p:creationdate>2025-06-21T20:34:35Z</p:creationdate>
                                <p:getlastmodified>Sat, 21 Jun 2025 20:34:35 GMT</p:getlastmodified>
                                <p:getetag>"e0-6381ae82aeb34"</p:getetag>
                                <D:supportedlock></D:supportedlock>
                                <D:getcontenttype>httpd/unix-directory</D:getcontenttype>
                            </D:prop>
                            <D:status>HTTP/1.1 200 OK</D:status>
                        </D:propstat>
                    </D:response>
                </D:multistatus>
                """,
                content_type='application/xml; charset="utf-8"',
                status=207
            )

        elif folder == '/webdav/' and file != '':
            id = _parse_ref(file)
            bookmark = Bookmark.objects.get(id=int(id))

            return HttpResponse(
                """<?xml version="1.0" encoding="utf-8" ?>
                <D:multistatus xmlns:D="DAV:" xmlns:p="http://apache.org/dav/props/">
                    {}
                </D:multistatus>
                """.format(_bookmark_to_response(bookmark)),
                content_type='application/xml; charset="utf-8"',
                status=207
            )

        else:
            return HttpResponse(
                """<?xml version="1.0" encoding="utf-8" ?>
                <multistatus xmlns="DAV:">
                  <response>
                    <href>{}</href>
                    <propstat>
                        <status>HTTP/1.1 404 Not Found</status>
                    </propstat>
                  </response>
                </multistatus>""".format(request.get_full_path()),
                content_type='application/xml; charset="utf-8"',
                status=207
            )

    def get(self, request, path, *args, **kwargs):
        folder, file = path_parts(path)
        file = _parse_ref(file)

        if file:
            bookmark = Bookmark.objects.filter(id=int(file)).first()
            print(str(bookmark))

            # asset = access.asset_read(request, asset_id)
            asset = BookmarkAsset.objects.get(
                pk=bookmark.latest_snapshot_body_id)
            content = _get_asset_content(asset)

            # asset = access.asset_read(request, asset_id)
            # bookmark = access.bookmark_read(request, asset.bookmark_id)
            content = _get_asset_content(asset)
            content = content.decode("utf-8")

            return render(
                request,
                "bookmarks/read.html",
                {
                    "content": content,
                    "bookmark": bookmark
                },
            )

        else:
            return HttpResponse(
                """<?xml version="1.0" encoding="utf-8" ?>
                <multistatus xmlns="DAV:">
                  <response>
                    <href>{}</href>
                    <propstat>
                        <status>HTTP/1.1 404 Not Found</status>
                    </propstat>
                  </response>
                </multistatus>""".format(request.get_full_path()),
                content_type='application/xml; charset="utf-8"',
                status=207
            )

    def post(self, request, *args, **kwargs):
        return self._forbidden(request)

    def put(self, request, *args, **kwargs):
        return self._forbidden(request)

    def proppatch(self, request, *args, **kwargs):
        return self._forbidden(request)

    def mkcol(self, request, path, *args, **kwargs):
        folder, file = path_parts(path)
        return HttpResponse(
            """<?xml version="1.0" encoding="utf-8" ?>
            <error xmlns="DAV:">
                <need-privileges>
                    <resource>
                        <href>{}</href>
                        <privilege><bind/></privilege>
                    </resource>
                </need-privileges>
                <responsedescription>Read-only filestystem.</responsedescription>
            </error>
            """.format(folder),
            content_type='application/xml; charset="utf-8"',
            status=403
        )

    def copy(self, request, *args, **kwargs):
        return self._forbidden(request)

    def move(self, request, *args, **kwargs):
        return self._forbidden(request)

    def lock(self, request, path, *args, **kwargs):
        folder, file = path_parts(path)
        return HttpResponse(
            """<?xml version="1.0" encoding="utf-8" ?>
            <error xmlns="DAV:">
                <need-privileges>
                    <resource>
                        <href>{}</href>
                        <privilege><bind/></privilege>
                    </resource>
                </need-privileges>
                <responsedescription>Read-only filestystem.</responsedescription>
            </error>
            """.format(folder),
            content_type='application/xml; charset="utf-8"',
            status=403
        )

    def _forbidden(self, request: HttpRequest, needed_privilege="<write-content/>"):
        return HttpResponse(
            """<?xml version="1.0" encoding="utf-8" ?>
            <error xmlns="DAV:">
                <need-privileges>
                    <resource>
                        <href>{}</href>
                        <privilege>{}</privilege>
                    </resource>
                </need-privileges>
                <responsedescription>Read-only filestystem.</responsedescription>
            </error>
            """.format(request.get_full_path(), needed_privilege),
            content_type='application/xml; charset="utf-8"',
            status=403
        )
