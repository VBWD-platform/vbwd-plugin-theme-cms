"""S152-06a §3 + §6 — the two template registries (twins of ``registerCmsPageType`` /
``registerCmsVueComponent``).

* ``PageTypeTemplateRegistry``: page, post, term_archive and archive ship; an
  unknown type falls back to ``page`` (``resolveCmsPageType`` → page); a later
  registration of the same type wins (``Map.set``).
* ``ComponentTemplateRegistry``: a component name maps to one template + its
  context builder; unknown names resolve to ``None`` (the renderer shows the
  missing-component comment); a duplicate name is refused (two adapters fighting
  over one component is a bug, not a preference).
"""
import pytest

from plugins.theme_cms.theme_cms.registries import (
    ComponentTemplate,
    ComponentTemplateRegistry,
    ComponentTemplateRegistrationError,
    PageTypeTemplateRegistry,
    default_page_type_registry,
)


def test_built_in_page_types_resolve_to_their_templates():
    registry = default_page_type_registry()

    assert registry.resolve("page") == "cms/page_types/page.html.j2"
    assert registry.resolve("post") == "cms/page_types/post.html.j2"
    assert registry.resolve("term_archive") == "cms/page_types/term_archive.html.j2"
    assert registry.resolve("archive") == "cms/page_types/archive.html.j2"


@pytest.mark.parametrize("unknown_type", ["video", "", None])
def test_unknown_page_types_fall_back_to_page(unknown_type):
    assert default_page_type_registry().resolve(unknown_type) == (
        "cms/page_types/page.html.j2"
    )


def test_a_later_page_type_registration_wins():
    registry = PageTypeTemplateRegistry()
    registry.register("video", "a.html.j2")
    registry.register("video", "b.html.j2")

    assert registry.resolve("video") == "b.html.j2"


def _component(name):
    return ComponentTemplate(
        name=name,
        template=f"cms/components/{name}.html.j2",
        build_context=lambda *args: {},
    )


def test_components_resolve_by_name_and_unknown_is_none():
    registry = ComponentTemplateRegistry()
    breadcrumb = _component("CmsBreadcrumb")
    registry.register(breadcrumb)

    assert registry.resolve("CmsBreadcrumb") is breadcrumb
    assert registry.resolve("ProductGrid") is None
    assert registry.resolve(None) is None


def test_a_duplicate_component_name_is_refused():
    registry = ComponentTemplateRegistry()
    registry.register(_component("ProductGrid"))

    with pytest.raises(ComponentTemplateRegistrationError, match="ProductGrid"):
        registry.register(_component("ProductGrid"))
