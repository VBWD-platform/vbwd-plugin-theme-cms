"""Seeds cms content through the cms admin HTTP API as the core test admin.

Theme adapters may not import ``plugins.cms`` (the D3 oracle walks tests too),
so the public admin surface is the service boundary used here. Everything is
written inside the test's rolled-back transaction, so nothing persists.
"""
import base64
import uuid

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "AdminPass123@"
ADMIN_API = "/api/v1/admin/cms"


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def encoded_html(html: str) -> str:
    return base64.b64encode(html.encode("utf-8")).decode("ascii")


class CmsAdminSeeder:
    def __init__(self, client):
        self._client = client
        login = client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        body = login.get_json()
        assert login.status_code == 200, body
        self.headers = {
            "Authorization": f"Bearer {body.get('token') or body.get('access_token')}"
        }

    def _send(self, method, path, payload, expected_status):
        response = self._client.open(
            f"{ADMIN_API}{path}", method=method, json=payload, headers=self.headers
        )
        assert response.status_code == expected_status, (path, response.get_json())
        return response.get_json()

    def style(self, css):
        return self._send(
            "POST", "/styles", {"name": unique("Style"), "source_css": css}, 201
        )

    def widget(self, widget_type, slug=None, **fields):
        payload = {
            "name": unique("Widget"),
            "slug": slug or unique("w"),
            "widget_type": widget_type,
            **fields,
        }
        return self._send("POST", "/widgets", payload, 201)

    def html_widget(self, html, **fields):
        return self.widget(
            "html", content_json={"content": encoded_html(html)}, **fields
        )

    def menu(self, widget_id, items):
        return self._send("PUT", f"/widgets/{widget_id}/menu", items, 200)

    def layout(self, areas, assignments=(), slug=None, **fields):
        layout = self._send(
            "POST",
            "/layouts",
            {
                "name": unique("Layout"),
                "slug": slug or unique("l"),
                "areas": areas,
                **fields,
            },
            201,
        )
        if assignments:
            self._send(
                "PUT", f"/layouts/{layout['id']}/widgets", list(assignments), 200
            )
        return layout

    def post(self, **fields):
        payload = {
            "type": "page",
            "status": "published",
            "title": unique("Title"),
            "slug": unique("p"),
            **fields,
        }
        return self._send("POST", "/posts", payload, 201)

    def post_widgets(self, post_id, assignments):
        return self._send("PUT", f"/posts/{post_id}/widgets", list(assignments), 200)

    def access_level(self, slug):
        """A core access level (core admin API is not needed: the test asserts the cms filter)."""
        from vbwd.extensions import db
        from vbwd.models.user_access_level import AccessLevel
        from vbwd.repositories.base import BaseRepository

        return BaseRepository(db.session, AccessLevel).save(
            AccessLevel(name=f"Theme cms {slug}", slug=slug)
        )

    # ── S152-06b component fixtures ──────────────────────────────────────

    def vue_widget(self, component, config=None, slug=None):
        """A ``vue-component`` widget, its component named as the admin UI stores it."""
        return self.widget(
            "vue-component",
            slug=slug,
            content_json={"component": component},
            config={"component_name": component, **(config or {})},
        )

    def term(self, term_type, name, slug=None):
        return self._send(
            "POST",
            "/terms",
            {"term_type": term_type, "name": name, "slug": slug or unique(term_type)},
            201,
        )

    def categorize(self, post, *terms):
        self._send(
            "PUT",
            f"/posts/{post['id']}/terms",
            {"term_ids": [t["id"] for t in terms]},
            200,
        )

    def tag(self, post, *slugs):
        """Tags live in the core tag index (``vbwd_entity_tag``), not in cms terms."""
        entity_type = "cms_page" if post.get("type") == "page" else "cms_post"
        for slug in slugs:
            created = self._client.post(
                "/api/v1/admin/tags",
                json={"slug": slug, "name": slug.title()},
                headers=self.headers,
            )
            assert created.status_code == 201, created.get_json()
        response = self._client.put(
            f"/api/v1/admin/{entity_type}/{post['id']}/tags",
            json={"tags": list(slugs)},
            headers=self.headers,
        )
        assert response.status_code == 200, response.get_json()

    def page_with_widgets(self, widgets, **post_fields):
        """A page whose layout puts each widget in its own area, after the content area."""
        areas = [{"name": "main", "type": "content"}] + [
            {"name": f"area{index}", "type": "header"} for index in range(len(widgets))
        ]
        layout = self.layout(
            areas,
            [
                {
                    "widget_id": widget["id"],
                    "area_name": f"area{index}",
                    "sort_order": 0,
                }
                for index, widget in enumerate(widgets)
            ],
        )
        return self.post(layout_id=layout["id"], **post_fields)

    def terms_archive_layout(self, client, widgets):
        """The ONE ``terms-archive`` layout (created, or re-assigned inside the rollback)."""
        areas = [
            {"name": f"area{index}", "type": "header"} for index in range(len(widgets))
        ]
        assignments = [
            {"widget_id": widget["id"], "area_name": f"area{index}", "sort_order": 0}
            for index, widget in enumerate(widgets)
        ]
        existing = client.get("/api/v1/cms/layouts/by-slug/terms-archive")
        if existing.status_code != 200:
            return self.layout(areas, assignments, slug="terms-archive")
        layout_id = existing.get_json()["id"]
        self._send("PUT", f"/layouts/{layout_id}", {"areas": areas}, 200)
        self._send("PUT", f"/layouts/{layout_id}/widgets", assignments, 200)
        return existing.get_json()
