# ADR-003: Cloudflare Access Authentication via williaby/testing Middleware

> **Status**: Accepted
> **Date**: 2025-12-04

## TL;DR

We will use Cloudflare Access for authentication, integrated via the williaby/testing cloudflare-auth Python middleware, because it provides Zero Trust security without managing our own identity provider while leveraging existing organizational Cloudflare infrastructure.

## Context

### Problem

The RAG WebUI requires authenticated access to:

- Control who can ingest files into the pipeline
- Provide audit trails (who submitted which batches)
- Prevent unauthorized access to job status and results
- Support WebSocket connections with authentication

### Constraints

- **Technical**: Must integrate with FastAPI gateway, support JWT validation, provide user context in API endpoints, work with WebSocket connections
- **Business**: Cloudflare Access already deployed for organizational infrastructure, no budget for third-party auth services (Auth0, etc.)

### Significance

Authentication is a security-critical decision that affects:

- **Security**: Weak auth = unauthorized pipeline access and data exposure
- **Compliance**: Audit requirements demand user attribution
- **UX**: Poor auth flow = user friction and abandonment
- **Operational**: Self-managed auth = maintenance burden (password resets, MFA, etc.)

## Decision

**We will use Cloudflare Access with the williaby/testing cloudflare-auth middleware because it provides production-grade authentication with zero operational overhead, leveraging existing organizational infrastructure.**

### Rationale

1. **Zero Trust Model**: Cloudflare Access enforces authentication before traffic reaches our services (defense in depth)
2. **No Identity Management**: OAuth, MFA, password policies managed by Cloudflare (reduces attack surface)
3. **Existing Infrastructure**: Organization already uses Cloudflare Tunnel and Access (no new accounts or billing)
4. **Drop-in Integration**: williaby/testing middleware provides FastAPI integration in <10 lines of code
5. **Audit Trail**: JWT contains email and user_id, automatically logged for compliance

## Options Considered

### Option 1: Cloudflare Access + williaby/testing Middleware ✓

**Pros**:

- ✅ Zero operational overhead (no user database, password management, MFA setup)
- ✅ JWT validation handled by middleware with automatic signature verification
- ✅ Granular access control via Cloudflare Access policies (email whitelists, IP restrictions)
- ✅ Local dev bypass mode (CLOUDFLARE_ENABLED=false) for offline development
- ✅ WebSocket authentication via token query parameter pattern

**Cons**:

- ❌ Vendor lock-in to Cloudflare ecosystem
- ❌ Requires Cloudflare Tunnel (acceptable: already deployed)

### Option 2: Self-Hosted OAuth (Keycloak)

**Pros**:

- ✅ Full control over identity provider
- ✅ No vendor lock-in

**Cons**:

- ❌ Operational burden (deploy, maintain, backup Keycloak database)
- ❌ Security responsibility (patch management, key rotation, breach response)
- ❌ Development time to integrate OAuth flow (2-3 weeks)
- ❌ Requires PostgreSQL for Keycloak (additional service)

### Option 3: API Keys

**Pros**:

- ✅ Simplest implementation

**Cons**:

- ❌ No user attribution (all requests appear from same "API key" user)
- ❌ Poor audit trail (cannot determine who submitted files)
- ❌ Key rotation complexity
- ❌ No MFA support

## Consequences

### Positive

- ✅ **Rapid Development**: Auth implementation complete in <1 day (middleware setup + config)
- ✅ **Production Security**: Cloudflare's global edge enforces auth before requests reach gateway
- ✅ **Compliance**: Every job automatically tagged with user email and user_id for audit logs
- ✅ **Zero Maintenance**: No password resets, account provisioning, or MFA management

### Trade-offs

- ⚠️ **Cloudflare Dependency**: Cannot easily migrate to different auth provider—mitigated by standardizing on CloudflareUser interface (abstraction layer)
- ⚠️ **JWT Cookie Handling**: Frontend must extract CF_Authorization cookie for WebSocket connections—documented in integration guide

### Technical Debt

- **User Role Management**: Current implementation treats all authenticated users equally (no admin/user roles)—if role-based access control becomes required, evaluate Cloudflare Access groups integration or add application-level RBAC (deferred to Phase 2)

## Implementation

### Components Affected

1. **Gateway Middleware**: CloudflareAuthMiddleware added to FastAPI app with excluded paths (/health, /metrics, /docs)
2. **API Endpoints**: All protected routes use `Depends(get_current_user)` to access CloudflareUser object
3. **WebSocket Handler**: Custom JWT validation from query parameter (Cloudflare token in CF_Authorization cookie)
4. **Environment Config**: CLOUDFLARE_TEAM_DOMAIN, CLOUDFLARE_AUDIENCE_TAG, CLOUDFLARE_ENABLED variables

### Testing Strategy

- **Unit**: Mock CloudflareUser in tests to avoid dependency on Cloudflare
- **Integration**: Test with real Cloudflare Access staging environment before production deployment
- **E2E**: Validate full auth flow (login redirect → JWT validation → API access → WebSocket connection)

## Validation

### Success Criteria

- [ ] Unauthenticated requests to /api/v1/ingest return 401 Unauthorized
- [ ] Authenticated requests include user.email and user.user_id in job audit fields
- [ ] WebSocket connections reject invalid or missing CF_Authorization tokens
- [ ] Local development mode (CLOUDFLARE_ENABLED=false) bypasses auth for rapid testing
- [ ] JWT signature validation prevents tampered tokens from granting access

### Review Schedule

- **Initial**: End of Phase 0 (week 1) - validate middleware integration and local dev workflow
- **Ongoing**: Re-evaluate if RBAC requirements emerge or Cloudflare dependency becomes limiting

## Related

- [ADR-001](./adr-001-initial-architecture.md) - References Cloudflare Access as authentication mechanism
- [Tech Spec](../tech-spec.md#security) - Details authentication flow and JWT validation
- [WebUI Spec](../../webui_spec.md#authentication--security) - Original authentication requirements
