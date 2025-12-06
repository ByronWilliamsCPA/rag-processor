"""Authentication module for RAG Processor.

Provides Cloudflare Access JWT validation and user context extraction.
"""

from rag_processor.auth.cloudflare import CloudflareAuthMiddleware
from rag_processor.auth.dependencies import get_current_user
from rag_processor.auth.models import CloudflareUser

__all__ = [
    "CloudflareAuthMiddleware",
    "CloudflareUser",
    "get_current_user",
]
