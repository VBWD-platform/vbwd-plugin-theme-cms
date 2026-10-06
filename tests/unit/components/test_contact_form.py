"""S152-06b — ContactForm (ContactForm.vue) and its POST fragment.

The form (testids cf-form / cf-submit / cf-field-<id> / cf-error-<id> /
cf-global-error / cf-success / cf-not-configured) posts through htmx to
``POST /_render/_fragment/cms/contact``. The fragment re-reads the widget config
(``GET /api/v1/cms/widgets/by-slug/<slug>``), validates required fields like
``validateForm`` and calls the SAME endpoint as the Vue component
(``POST /api/v1/contact`` with ``{widget_slug, _hp, fields}``): 429 → the
rate-limited copy, another error → the API message (else the generic copy),
success → the success state. Values survive a failed submit.
"""
import pytest
from werkzeug.datastructures import MultiDict

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_cms.tests.unit.components.fakes import FakeCmsApi, FakeThemeRequest
from plugins.theme_cms.tests.unit.dom_contract import canonical, testids
from plugins.theme_cms.tests.unit.template_harness import render_component, theme_plugin
from plugins.theme_cms.theme_cms.components.contact_form import (
    CONTACT_FRAGMENT_PATH,
    build_contact_form_context,
    build_contact_fragment_context,
)

TEMPLATE = "cms/components/contact_form.html.j2"
FIELDS = [
    {"id": "name", "type": "text", "label": "Name", "required": True},
    {"id": "message", "type": "textarea", "label": "Message"},
    {
        "id": "plan",
        "type": "radio",
        "label": "Plan",
        "options": ["A", "B"],
        "required": False,
    },
    {"id": "topics", "type": "checkbox", "label": "Topics", "options": ["X", "Y"]},
]
CONFIG = {
    "component_name": "ContactForm",
    "recipient_email": "team@example.com",
    "fields": FIELDS,
    "widget_slug": "contact-us",
}


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _render(context):
    return render_component(theme_plugin(), TEMPLATE, context)


def _post_request(form):
    request = FakeThemeRequest(path=CONTACT_FRAGMENT_PATH)
    request.query_args = MultiDict(form)
    return request


def test_the_form_markup_matches_the_vue_template():
    html = _render(build_contact_form_context(CONFIG, {}, {}, FakeThemeRequest()))

    assert canonical(html) == canonical(
        '<div class="contact-form-widget">'
        '<form class="contact-form-widget__form" data-testid="cf-form" novalidate '
        f'method="post" action="{CONTACT_FRAGMENT_PATH}" hx-post="{CONTACT_FRAGMENT_PATH}" '
        'hx-target="closest .contact-form-widget" hx-swap="outerHTML" '
        'hx-disabled-elt="find .contact-form-widget__submit">'
        '<input type="hidden" name="widget_slug" value="contact-us">'
        '<div class="contact-form-widget__hp" aria-hidden="true" '
        'style="display:none !important; position:absolute; left:-9999px;">'
        '<label for="_cf_hp">Leave blank</label>'
        '<input id="_cf_hp" type="text" name="_hp" tabindex="-1" autocomplete="off" value="">'
        "</div>"
        '<div class="contact-form-widget__field">'
        '<label for="cf_name" class="contact-form-widget__label">Name'
        '<span class="contact-form-widget__required" aria-hidden="true">*</span></label>'
        '<input id="cf_name" class="contact-form-widget__input" type="text" name="name" '
        'required aria-required="true" data-testid="cf-field-name" value="">'
        "</div>"
        '<div class="contact-form-widget__field">'
        '<label for="cf_message" class="contact-form-widget__label">Message</label>'
        '<textarea id="cf_message" class="contact-form-widget__input contact-form-widget__textarea" '
        'name="message" rows="4" data-testid="cf-field-message"></textarea>'
        "</div>"
        '<div class="contact-form-widget__field">'
        '<label for="cf_plan" class="contact-form-widget__label">Plan</label>'
        '<div class="contact-form-widget__radio-group" data-testid="cf-field-plan">'
        '<label class="contact-form-widget__option"><input type="radio" name="plan" value="A">A</label>'
        '<label class="contact-form-widget__option"><input type="radio" name="plan" value="B">B</label>'
        "</div></div>"
        '<div class="contact-form-widget__field">'
        '<label for="cf_topics" class="contact-form-widget__label">Topics</label>'
        '<div class="contact-form-widget__checkbox-group" data-testid="cf-field-topics">'
        '<label class="contact-form-widget__option"><input type="checkbox" name="topics" value="X">X</label>'
        '<label class="contact-form-widget__option"><input type="checkbox" name="topics" value="Y">Y</label>'
        "</div></div>"
        '<button type="submit" class="contact-form-widget__submit" data-testid="cf-submit">'
        "Send Message</button>"
        "</form></div>"
    )


def test_without_a_recipient_the_form_is_not_configured():
    context = build_contact_form_context({"fields": FIELDS}, {}, {}, FakeThemeRequest())

    assert canonical(_render(context)) == canonical(
        '<div class="contact-form-widget"><div class="contact-form-widget__error" '
        'data-testid="cf-not-configured"><p>This contact form is not yet configured.</p></div></div>'
    )


def test_captcha_and_analytics_html_are_raw_like_v_html_and_css_cannot_break_out():
    config = {
        **CONFIG,
        "captcha_html": '<div class="g-recaptcha" data-sitekey="k"></div>',
        "analytics_html": "<script>window.cf = 1</script>",
        "css": ".contact-form-widget{color:red}</style><b>x</b>",
    }

    html = _render(build_contact_form_context(config, {}, {}, FakeThemeRequest()))

    assert (
        '<div class="contact-form-widget__captcha"><div class="g-recaptcha" data-sitekey="k"></div></div>'
        in html
    )
    assert (
        '<div class="contact-form-widget__analytics"><script>window.cf = 1</script></div>'
        in html
    )
    assert (
        "<style data-contact-form-css>.contact-form-widget{color:red}<\\/style><b>x</b></style>"
        in html
    )


def test_field_labels_options_and_ids_are_escaped():
    config = {
        **CONFIG,
        "fields": [
            {"id": 'x"y', "type": "radio", "label": "<b>L</b>", "options": ["<i>o</i>"]}
        ],
    }

    html = _render(build_contact_form_context(config, {}, {}, FakeThemeRequest()))

    assert "<b>L</b>" not in html and "&lt;b&gt;L&lt;/b&gt;" in html
    assert "<i>o</i>" not in html
    assert 'data-testid="cf-field-x&#34;y"' in html


def test_a_missing_required_field_re_renders_the_form_with_its_error_and_values():
    cms_api = FakeCmsApi(widget_by_slug={"slug": "contact-us", "config": CONFIG})
    request = _post_request(
        [
            ("widget_slug", "contact-us"),
            ("name", "  "),
            ("message", "Hi <there>"),
            ("topics", "Y"),
        ]
    )

    context = build_contact_fragment_context(request, cms_api.factory)
    html = _render(context["component_context"])

    assert [call[0] for call in cms_api.calls] == ["widget_by_slug"]
    assert (
        '<p class="contact-form-widget__field-error" role="alert" data-testid="cf-error-name">'
        "Name is required.</p>"
    ) in html
    assert ">Hi &lt;there&gt;</textarea>" in html
    assert '<input type="checkbox" name="topics" value="Y" checked>' in html
    assert '<input type="checkbox" name="topics" value="X">' in html


def test_a_valid_submit_posts_the_vue_payload_and_shows_the_success_state():
    cms_api = FakeCmsApi(
        widget_by_slug={
            "slug": "contact-us",
            "config": {**CONFIG, "success_message": "Thanks!"},
        },
        submit_contact={"ok": True},
    )
    request = _post_request(
        [
            ("widget_slug", "contact-us"),
            ("_hp", ""),
            ("name", "Ada"),
            ("message", "Hello"),
            ("plan", "B"),
            ("topics", "X"),
            ("topics", "Y"),
        ]
    )

    context = build_contact_fragment_context(request, cms_api.factory)
    html = _render(context["component_context"])

    assert cms_api.calls[1] == (
        "submit_contact",
        {
            "widget_slug": "contact-us",
            "_hp": "",
            "fields": {
                "name": "Ada",
                "message": "Hello",
                "plan": "B",
                "topics": ["X", "Y"],
            },
        },
    )
    assert canonical(html) == canonical(
        '<div class="contact-form-widget"><div class="contact-form-widget__success" '
        'data-testid="cf-success"><p>Thanks!</p></div></div>'
    )


def test_the_default_success_copy_is_used_without_a_configured_message():
    cms_api = FakeCmsApi(
        widget_by_slug={"slug": "contact-us", "config": CONFIG},
        submit_contact={"ok": True},
    )

    context = build_contact_fragment_context(
        _post_request([("widget_slug", "contact-us"), ("name", "Ada")]), cms_api.factory
    )

    assert "Thank you! We will get back to you soon." in _render(
        context["component_context"]
    )


@pytest.mark.parametrize(
    "api_error, message",
    [
        (ThemeApiError(429, "Too many"), "Too many requests. Please try again later."),
        (ThemeApiError(422, "Invalid email"), "Invalid email"),
        (ThemeApiError(500, ""), "Something went wrong. Please try again."),
    ],
)
def test_an_api_refusal_is_the_global_error_and_keeps_the_form(api_error, message):
    cms_api = FakeCmsApi(
        widget_by_slug={"slug": "contact-us", "config": CONFIG},
        submit_contact=api_error,
    )

    context = build_contact_fragment_context(
        _post_request([("widget_slug", "contact-us"), ("name", "Ada")]), cms_api.factory
    )
    html = _render(context["component_context"])

    assert (
        '<p class="contact-form-widget__error-msg" role="alert" data-testid="cf-global-error">'
        f"{message}</p>"
    ) in html
    assert 'value="Ada"' in html
    assert "cf-form" in testids(html)
