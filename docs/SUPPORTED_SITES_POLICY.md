# Supported Sites and Integration Policy

This document explains what goster.me means by technical support for a site and how requests for new support, compatibility fixes, or removal are handled.

Turkish is the primary product and policy language for this project. This English version provides the same practical information for non-Turkish users, contributors, and site owners.

## What does "supported" mean?

When goster.me lists a site as **supported**, it means technical compatibility only.

It does not imply partnership, sponsorship, official endorsement, a commercial relationship, content ownership, or that goster.me acts on behalf of the site owner.

goster.me is intended to present content explicitly requested by the user in a simpler view with unnecessary distractions reduced where technically appropriate.

## Supported-sites catalog

A single canonical catalog will describe supported sites and providers. As the adapter refactor progresses, this catalog should be derived as closely as possible from the same explicit adapter registry used by the application, rather than being maintained as a separate manual list.

The public catalog may include, where useful, the site/provider name, support mode (`embed`, `isolate`, etc.), important known limitations, and support status. It should not disclose unnecessary infrastructure or security details.

## Requesting support for a new site

A user, contributor, or site owner may request support for a new site or content type. Initially, opening a GitHub Issue is sufficient.

A useful request should include an example URL, the primary content that should be shown, what currently fails or appears unnecessarily, and any short technical note that may help reproduce the case.

Support is not guaranteed. Requests are evaluated against security, technical feasibility, maintainability, source-site behavior, and goster.me's content-minimization goals.

## Reporting an integration problem

A GitHub Issue may also be used when content is incomplete or incorrect, a required control no longer works, unnecessary source-page content remains, external navigation escapes the intended view, advertising/tracking execution remains, or a source-site change breaks an adapter.

Please include an example URL and observed behavior where possible.

## Requesting removal or exclusion as a site owner

A site owner or authorized representative who does not want their site processed by goster.me may open a **removal / exclusion request** through GitHub Issues.

The process should remain low-friction. When necessary, reasonable evidence may be requested to establish that the requester is the site owner or an authorized representative.

Verified removal requests should be handled as promptly and transparently as practical. Depending on scope, removal may include disabling the relevant domain or content family in adapter matching and updating the support catalog, tests, and documentation.

Security and abuse-prevention controls remain in force throughout this process.

## Re-inclusion or changing scope

A previously excluded site may later request re-inclusion, or request that only specific content families be supported. Such requests can be discussed in a new Issue and are evaluated using the same security, feasibility, and maintainability criteria.

## Transparency and tracking

Where appropriate, support, compatibility, and removal requests should remain traceable through GitHub so that the request, decision, implementation, and validation can be understood later.

Do not place security vulnerabilities, personal data, or other sensitive information in a public Issue. A suitable private reporting path will be documented separately for those cases.

## Language policy

Turkish is the primary language for goster.me's initial audience and is designed first for public product and policy text.

English has secondary presentation priority, but not reduced substance. A non-Turkish user, contributor, or site owner should be able to understand the same processes, options, and material policy terms in English.

The two language versions should not intentionally differ in policy substance.

## Implementation note

This document defines the policy contract. The actual supported-sites list will be generated from the canonical adapter/provider catalog created alongside the modular adapter refactor.

Tracking: GitHub Issue #11 — `Publish supported-sites catalog and inclusion/exclusion policy`.
