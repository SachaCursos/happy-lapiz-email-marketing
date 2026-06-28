"""Backward-compatible re-export. Use template_compositions instead."""

from app.services.template_compositions import ensure_managed_block_templates

ensure_catalog_templates = ensure_managed_block_templates
