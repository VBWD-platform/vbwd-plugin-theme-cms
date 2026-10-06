/**
 * S152 walkthrough @theme_cms — a reader's tour of the themed CMS: home → a post (hero,
 * layout areas, breadcrumb) → its category archive → a paginated blog index → search
 * (quicksearch dropdown, then results) → the contact form → the cookie banner (accept,
 * then it stays closed) → the chrome-light embed archive.
 *
 * Seeds (admin API, removed afterwards): a category with three posts, their layout
 * (breadcrumb + sidebar), and pages for the archive, search, contact form and consent.
 */
import { test, expect, type Page } from '@playwright/test';
import { uniqueSlug } from '@fe-user-e2e/frontend-mode/frontend-mode-support';
import {
  AdminSeeder,
  WalkthroughSteps,
  skipUnlessThemeMode,
} from '../../../theme/tests/e2e/support/walkthrough-support';

const CMS_ADMIN = '/api/v1/admin/cms';
const POSTS_PER_ARCHIVE_PAGE = 2;
/** Above the consent version every e2e context is seeded with (consent-storage-state.ts). */
const WALKTHROUGH_CONSENT_VERSION = 5000;
const CONSENT_STORAGE_KEY = 'vbwd_cookie_consent';
const CONTACT_SUCCESS_MESSAGE = 'Thanks — the walkthrough message arrived.';

interface SeededPost {
  id: string;
  slug: string;
  title: string;
}

class CmsWalkthroughSeed {
  constructor(private readonly seeder: AdminSeeder) {}

  term(name: string) {
    return this.seeder.create(`${CMS_ADMIN}/terms`, { term_type: 'category', name }, (term) => `${CMS_ADMIN}/terms/${term.id}`);
  }

  vueWidget(component: string, config: Record<string, unknown>) {
    return this.seeder.create(
      `${CMS_ADMIN}/widgets`,
      {
        name: uniqueSlug(`Walkthrough ${component}`),
        slug: uniqueSlug(`walkthrough-${component.toLowerCase()}`),
        widget_type: 'vue-component',
        content_json: { component },
        config: { component_name: component, ...config },
      },
      (widget) => `${CMS_ADMIN}/widgets/${widget.id}`,
    );
  }

  htmlWidget(html: string) {
    return this.seeder.create(
      `${CMS_ADMIN}/widgets`,
      {
        name: uniqueSlug('Walkthrough html'),
        slug: uniqueSlug('walkthrough-html'),
        widget_type: 'html',
        content_json: { content: Buffer.from(html, 'utf-8').toString('base64') },
      },
      (widget) => `${CMS_ADMIN}/widgets/${widget.id}`,
    );
  }

  /** A layout whose areas each hold one widget: `[areaName, areaType, widgetId]`. */
  async layout(areas: Array<[string, string, string | null]>) {
    const layout = await this.seeder.create(
      `${CMS_ADMIN}/layouts`,
      {
        name: uniqueSlug('Walkthrough layout'),
        slug: uniqueSlug('walkthrough-layout'),
        areas: areas.map(([name, type]) => ({ name, type, label: name })),
      },
      (created) => `${CMS_ADMIN}/layouts/${created.id}`,
    );
    const assignments = areas
      .filter(([, , widgetId]) => widgetId !== null)
      .map(([areaName, , widgetId]) => ({ widget_id: widgetId, area_name: areaName, sort_order: 0 }));
    await this.seeder.send('PUT', `${CMS_ADMIN}/layouts/${layout.id}/widgets`, assignments);
    return layout;
  }

  async post(fields: Record<string, unknown>): Promise<SeededPost> {
    const post = await this.seeder.create(
      `${CMS_ADMIN}/posts`,
      { status: 'published', ...fields },
      (created) => `${CMS_ADMIN}/posts/${created.id}`,
    );
    return { id: post.id, slug: post.slug, title: post.title };
  }

  async categorisedPost(title: string, termId: string, layoutId: string, body: string): Promise<SeededPost> {
    const post = await this.post({
      type: 'post',
      title,
      excerpt: `${title} — a short excerpt for the archive card.`,
      content_html: `<p>${body}</p>`,
      layout_id: layoutId,
      term_ids: [termId],
      primary_term_id: termId,
    });
    await this.seeder.send('PUT', `${CMS_ADMIN}/posts/${post.id}/terms`, { term_ids: [termId] });
    return post;
  }

  page(title: string, layoutId: string) {
    return this.post({ type: 'page', title, slug: uniqueSlug('walkthrough-cms'), layout_id: layoutId, content_html: `<p>${title}</p>` });
  }
}

async function cardTitles(page: Page): Promise<string> {
  return (await page.locator('[data-testid="post-card"]').allInnerTexts()).join(' | ');
}

test.describe('Walkthrough @theme_cms — home, post, archives, search, contact, consent, embed', () => {
  skipUnlessThemeMode(test);

  const steps = new WalkthroughSteps('theme_cms');
  const searchToken = `walkzebra${Date.now()}`;
  const sidebarText = uniqueSlug('Walkthrough sidebar');
  let seeder: AdminSeeder;
  let category: Record<string, any>;
  let posts: SeededPost[];
  let archivePage: SeededPost;
  let searchPage: SeededPost;
  let contactPage: SeededPost;
  let consentPage: SeededPost;

  test.beforeAll(async () => {
    seeder = await AdminSeeder.open();
    const seed = new CmsWalkthroughSeed(seeder);
    category = await seed.term(uniqueSlug('Walkthrough Category'));
    const breadcrumb = await seed.vueWidget('CmsBreadcrumb', { root_name: 'Home', root_slug: '/', separator: '/', max_label_length: 60 });
    const sidebar = await seed.htmlWidget(`<aside data-testid="walkthrough-sidebar">${sidebarText}</aside>`);
    const postArchive = await seed.vueWidget('PostArchive', { mode: 'category', type: 'post', paginate: true, posts_per_page: POSTS_PER_ARCHIVE_PAGE });
    const search = await seed.vueWidget('Search', { placeholder: 'Search…', quicksearch: true, quicksearch_limit: 6, scope: 'posts', target_path: '' });
    const searchResults = await seed.vueWidget('SearchResults', { mode: 'category', per_page: 8, scope: 'posts' });
    const contactForm = await seed.vueWidget('ContactForm', {
      fields: [
        { id: 'name', label: 'Name', required: true, type: 'text' },
        { id: 'email', label: 'Email', required: true, type: 'email' },
        { id: 'message', label: 'Message', required: false, type: 'textarea' },
      ],
      recipient_email: 'walkthrough@example.com',
      success_message: CONTACT_SUCCESS_MESSAGE,
      rate_limit_enabled: false,
    });
    const cookieConsent = await seed.vueWidget('CookieConsent', {
      categories: ['necessary', 'statistics', 'marketing', 'preferences'],
      consent_version: WALKTHROUGH_CONSENT_VERSION,
      position: 'center',
      backdrop_opacity: 0.55,
      privacy_policy_url: '/privacy',
      show_settings_button: true,
    });

    const postLayout = await seed.layout([
      ['breadcrumbs', 'vue', breadcrumb.id],
      ['content', 'content', null],
      ['sidebar', 'header', sidebar.id],
    ]);
    const archiveLayout = await seed.layout([['content', 'content', null], ['archive', 'vue', postArchive.id]]);
    const searchLayout = await seed.layout([['search', 'vue', search.id], ['results', 'vue', searchResults.id]]);
    const contactLayout = await seed.layout([['content', 'content', null], ['contact form', 'vue', contactForm.id]]);
    const consentLayout = await seed.layout([['content', 'content', null], ['consent', 'vue', cookieConsent.id]]);

    posts = [];
    for (const name of ['Alpha', 'Beta', 'Gamma']) {
      posts.push(await seed.categorisedPost(`Walkthrough ${name} ${searchToken}`, category.id, postLayout.id, `${searchToken} ${name} body`));
    }
    archivePage = await seed.page('Walkthrough blog index', archiveLayout.id);
    searchPage = await seed.page('Walkthrough search', searchLayout.id);
    contactPage = await seed.page('Walkthrough contact', contactLayout.id);
    consentPage = await seed.page('Walkthrough privacy', consentLayout.id);
  });

  test.afterAll(async () => {
    await seeder?.cleanup();
  });

  test('a reader browses, searches, writes in and accepts cookies on the themed CMS @theme_cms', async ({ page }) => {
    const [firstPost] = posts;

    await page.goto('/');
    await steps.themed(page, '01-home');

    await page.goto(`/${firstPost.slug}`);
    await expect(page.locator('.cms-post-hero h1.cms-post-title')).toHaveText(firstPost.title);
    await expect(page.locator('.cms-post-hero .cms-post-excerpt')).toBeVisible();
    await expect(page.locator('[data-testid="walkthrough-sidebar"]')).toHaveText(sidebarText);
    const breadcrumb = page.locator('nav.vbwd-breadcrumb');
    await expect(breadcrumb.locator('a').first()).toHaveText('Home');
    await expect(breadcrumb.locator('.vbwd-breadcrumb__current')).toHaveCount(1);
    await steps.themed(page, '02-post-hero-areas-breadcrumb');

    await page.goto(`/category/${category.slug}`);
    await expect(page.locator('[data-testid="term-archive-heading"]')).toHaveText(category.name);
    await expect(page.locator('[data-testid="post-card"]')).toHaveCount(posts.length);
    expect(await cardTitles(page)).toContain(firstPost.title);
    await steps.themed(page, '03-category-archive');

    await page.goto(`/${archivePage.slug}`);
    await expect(page.locator('[data-testid="post-card"]')).toHaveCount(POSTS_PER_ARCHIVE_PAGE);
    await expect(page.locator('.post-archive-widget__page-indicator')).toContainText(/^1 \/ \d+$/);
    await page.locator('[data-testid="post-archive-next"]').click();
    await expect(page.locator('.post-archive-widget__page-indicator')).toContainText(/^2 \/ \d+$/);
    await steps.themed(page, '04-archive-page-2');

    await page.goto(`/${searchPage.slug}`);
    const searchBox = page.locator('[data-testid="post-search-input"]');
    await searchBox.fill(searchToken);
    await expect(page.locator('[data-testid="post-search-dropdown"]')).toBeVisible();
    await expect(page.locator('[data-testid="post-search-option"]')).toHaveCount(posts.length);
    await steps.themed(page, '05-quicksearch-dropdown');
    await searchBox.press('Enter');
    await expect(page).toHaveURL(new RegExp(`\\?q=${searchToken}`));
    await expect(page.locator('[data-testid="post-card"]')).toHaveCount(posts.length);
    for (const post of posts) {
      expect(await cardTitles(page)).toContain(post.title);
    }
    await steps.themed(page, '06-search-results');

    await page.goto(`/${contactPage.slug}`);
    await page.fill('[data-testid="cf-field-name"]', 'Walkthrough Reader');
    await page.fill('[data-testid="cf-field-email"]', 'reader@example.com');
    await page.fill('[data-testid="cf-field-message"]', 'Hello from the themed walkthrough.');
    await page.click('[data-testid="cf-submit"]');
    await expect(page.locator('[data-testid="cf-success"]')).toHaveText(CONTACT_SUCCESS_MESSAGE);
    await steps.themed(page, '07-contact-sent');

    await page.goto(`/${consentPage.slug}`);
    await expect(page.locator('[data-testid="cookie-consent-backdrop"]')).toBeVisible();
    await steps.themed(page, '08-consent-banner');
    await page.click('[data-testid="cookie-accept-all"]');
    await expect(page.locator('[data-testid="cookie-consent-backdrop"]')).toBeHidden();
    const storedConsent = await page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? '{}'), CONSENT_STORAGE_KEY);
    expect(storedConsent.version).toBe(WALKTHROUGH_CONSENT_VERSION);
    await page.reload();
    await expect(page.locator('[data-testid="cookie-consent-backdrop"]')).toBeHidden();
    await steps.themed(page, '09-consent-persisted');

    await page.goto(`/cms/embed/post/${category.slug}`);
    await expect(page.locator('[data-testid="post-card"]')).toHaveCount(posts.length);
    await expect(page.locator('[data-testid="post-card"] a[href^="/cms/embed/"]').first()).toBeVisible();
    await steps.themed(page, '10-embed-archive');
  });
});
