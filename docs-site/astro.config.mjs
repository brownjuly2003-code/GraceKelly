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
            { label: 'Execution adapters', slug: 'architecture/adapters' },
            { label: 'API routes catalog', slug: 'architecture/routes' },
            { label: 'Configuration matrix', slug: 'architecture/config' },
          ],
        },
        {
          label: 'Operations',
          items: [
            { label: 'Quickstart (RU)', slug: 'guides/quickstart-ru' },
            { label: 'Operator runbook', slug: 'guides/operator-runbook' },
            { label: 'Onboarding', slug: 'guides/onboarding' },
            { label: 'Perplexity DOM recon', slug: 'guides/perplexity-dom-recon' },
          ],
        },
        {
          label: 'Plans & history',
          items: [
            { label: 'Phased roadmap', slug: 'guides/phased-roadmap' },
            { label: 'Architecture notes', slug: 'guides/architecture' },
            { label: '2026-04-23 final closure', slug: 'guides/plans/2026-04-23-final-closure' },
            { label: '2026-04-25 open-questions handoff', slug: 'guides/plans/2026-04-25-open-questions-handoff' },
            { label: '2026-04-26 handoff', slug: 'guides/plans/2026-04-26-handoff' },
          ],
        },
        {
          label: 'Audits & gates',
          items: [
            { label: 'Post phase-2 audit (2026-04-23)', slug: 'guides/audits/2026-04-23-post-phase-2-audit' },
            { label: 'Dry-run gate audit (2026-04-25)', slug: 'guides/audits/2026-04-25-dry-run-gate-audit' },
            { label: 'Gate-2 operational review (2026-04-23)', slug: 'guides/gates/2026-04-23-gate-2-operational-review' },
            { label: 'Gate-3 execution-policy review (2026-04-23)', slug: 'guides/gates/2026-04-23-gate-3-execution-policy-review' },
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
      ],
      customCss: ['./src/assets/custom.css'],
    }),
  ],
});
