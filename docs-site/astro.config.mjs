// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://brownjuly2003-code.github.io',
  base: '/GraceKelly',
  integrations: [
    starlight({
      title: 'GraceKelly',
      description:
        'Internal codebase docs for GraceKelly — multi-model FastAPI orchestrator with browser execution adapters.',
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/brownjuly2003-code/GraceKelly',
        },
      ],
      sidebar: [
        { label: 'Home', slug: 'index' },
        {
          label: 'Architecture',
          items: [
            { label: 'Overview', slug: 'architecture' },
            { label: 'Execution modes', slug: 'architecture/execution-modes' },
            { label: 'API reference', slug: 'architecture/api' },
            { label: 'Error handling', slug: 'architecture/errors' },
            { label: 'Execution adapters', slug: 'architecture/adapters' },
            { label: 'Routes catalog', slug: 'architecture/routes' },
            { label: 'Configuration matrix', slug: 'architecture/config' },
          ],
        },
        {
          label: 'Operations',
          items: [
            { label: 'Getting started', slug: 'getting-started' },
            { label: 'Quickstart (RU)', slug: 'guides/quickstart-ru' },
            { label: 'Operator runbook', slug: 'guides/operator-runbook' },
            { label: 'Onboarding', slug: 'guides/onboarding' },
            { label: 'Perplexity DOM recon', slug: 'guides/perplexity-dom-recon' },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'Project overview (README)', slug: 'guides/overview' },
            { label: 'Agents protocol', slug: 'guides/agents' },
            { label: 'Claude protocol', slug: 'guides/claude' },
          ],
        },
        {
          label: 'Project history',
          collapsed: true,
          items: [
            { label: 'Phased roadmap', slug: 'guides/phased-roadmap' },
            { label: 'Architecture notes', slug: 'guides/architecture' },
          ],
        },
      ],
      customCss: [
        '@fontsource-variable/geist/index.css',
        '@fontsource-variable/geist-mono/index.css',
        './src/assets/custom.css',
      ],
    }),
  ],
});
