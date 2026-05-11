---
title: "Handoff Document: Document Context Preservation for Foundry-Unify"
schema_type: planning
status: draft
owner: core-maintainer
purpose: "Handoff specifications for implementing hierarchical document indexing to enhance RAG accuracy."
component: Strategy
source: "Foundry-Unify integration planning"
tags:
  - planning
  - architecture
---

> **From**: Project A (Prepare-Doc) Team
> **To**: Foundry-Unify Team
> **Date**: January 27, 2026
> **Subject**: Implementing Hierarchical Document Indexing for Enhanced RAG Accuracy
> **Priority**: High - Architectural Enhancement

---

## Executive Summary

Recent research demonstrates that **traditional vector RAG achieves only 19% accuracy on complex documents** (FinanceBench benchmark), while hierarchical/reasoning-based approaches achieve **98.7%**. The root cause is loss of document context (TOC, chapters, sections, page numbers) during chunking.

**Your existing Docling DOM integration already extracts this structure.** This handoff provides specifications for preserving it in a new `DocumentIndex` output that enables hybrid retrieval downstream.

---

## 1. Problem Statement

### Why Traditional RAG Fails

When documents are chunked for embedding:

```
Original Document                    After Chunking
─────────────────                    ──────────────
Chapter 3: Financial Results         [Chunk 47]: "Revenue grew 15%..."
  Section 3.1: Q3 Performance        [Chunk 48]: "Operating margin..."
    "Revenue grew 15%..."            [Chunk 49]: "See Table 3.2..."
    Table 3.2: Revenue by Region     [Chunk 50]: "North America: $2.1B"
```

**Lost Information**:
- "Revenue grew 15%" was in Chapter 3, Section 3.1
- "North America: $2.1B" came from Table 3.2 on page 47
- The table is related to the preceding paragraph
- Reading order and logical flow

### The FinanceBench Evidence

| Retrieval Method | Accuracy |
|-----------------|----------|
| GPT-4-Turbo + Vector RAG | **19%** |
| GPT-4-Turbo + Long Context | 50% |
| PageIndex (Hierarchical Tree) | **98.7%** |

Source: [FinanceBench](https://arxiv.org/abs/2311.11944), [PageIndex](https://github.com/VectifyAI/PageIndex)

---

## 2. Solution: Hierarchical Document Index

### Architecture Change

**Current Flow**:
```
Docling DOM → Normalized JSON → Chunk Stage → Embed Stage → Vector DB
                                    ↓
                              (structure lost)
```

**Enhanced Flow**:
```
Docling DOM → Normalized JSON ────────────────→ Chunk Stage → Embed Stage
           ↘                                         ↓
             DocumentIndex.json ──────────────→ (tree node IDs preserved)
                    ↓
             Reasoning Retrieval Path (new capability)
```

### What Unify Produces (New)

In addition to the existing normalized JSON output, generate a **`DocumentIndex.json`** that captures hierarchical structure.

---

## 3. Technical Specification: DocumentIndex Schema

### 3.1 Root Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "DocumentIndex",
  "description": "Hierarchical index for reasoning-based RAG retrieval",
  "type": "object",
  "required": ["schema_version", "document_id", "title", "tree", "page_boundaries"],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "1.0.0"
    },
    "document_id": {
      "type": "string",
      "description": "Unique identifier matching the source document"
    },
    "source_file": {
      "type": "string",
      "description": "Original filename"
    },
    "title": {
      "type": "string",
      "description": "Document title extracted from metadata or first heading"
    },
    "document_type": {
      "type": "string",
      "enum": ["report", "manual", "article", "form", "correspondence", "unknown"],
      "description": "High-level document classification"
    },
    "total_pages": {
      "type": "integer",
      "minimum": 1
    },
    "extraction_timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "tree": {
      "$ref": "#/$defs/TreeNode"
    },
    "page_boundaries": {
      "type": "array",
      "items": { "$ref": "#/$defs/PageBoundary" }
    },
    "detected_toc": {
      "$ref": "#/$defs/DetectedTOC",
      "description": "Explicit TOC if detected in document"
    }
  }
}
```

### 3.2 TreeNode Schema

```json
{
  "$defs": {
    "TreeNode": {
      "type": "object",
      "required": ["node_id", "title", "level", "start_page", "end_page"],
      "properties": {
        "node_id": {
          "type": "string",
          "pattern": "^[0-9]{4}$",
          "description": "Hierarchical identifier (e.g., '0001', '0002')"
        },
        "parent_id": {
          "type": ["string", "null"],
          "description": "Parent node_id, null for root"
        },
        "title": {
          "type": "string",
          "description": "Section/chapter heading"
        },
        "level": {
          "type": "integer",
          "minimum": 0,
          "maximum": 6,
          "description": "0=document, 1=chapter, 2=section, 3=subsection, etc."
        },
        "start_page": {
          "type": "integer",
          "minimum": 0,
          "description": "0-indexed first page of this section"
        },
        "end_page": {
          "type": "integer",
          "minimum": 0,
          "description": "0-indexed last page of this section (inclusive)"
        },
        "start_offset": {
          "type": "integer",
          "description": "Character offset in full document text"
        },
        "end_offset": {
          "type": "integer",
          "description": "Character offset end in full document text"
        },
        "summary": {
          "type": ["string", "null"],
          "description": "Optional LLM-generated or extracted summary (for RAPTOR-style)"
        },
        "section_type": {
          "type": "string",
          "enum": [
            "title_page", "toc", "chapter", "section", "subsection",
            "appendix", "glossary", "index", "references", "unknown"
          ]
        },
        "contains_tables": {
          "type": "boolean",
          "default": false
        },
        "contains_figures": {
          "type": "boolean",
          "default": false
        },
        "contains_equations": {
          "type": "boolean",
          "default": false
        },
        "docling_element_ids": {
          "type": "array",
          "items": { "type": "string" },
          "description": "References to Docling DOM element IDs for traceability"
        },
        "children": {
          "type": "array",
          "items": { "$ref": "#/$defs/TreeNode" },
          "default": []
        }
      }
    }
  }
}
```

### 3.3 PageBoundary Schema

```json
{
  "PageBoundary": {
    "type": "object",
    "required": ["page_number", "start_offset", "end_offset"],
    "properties": {
      "page_number": {
        "type": "integer",
        "minimum": 0,
        "description": "0-indexed page number"
      },
      "physical_page_label": {
        "type": ["string", "null"],
        "description": "Printed page number (e.g., 'iv', '42', 'A-1')"
      },
      "start_offset": {
        "type": "integer",
        "description": "Character offset where page content begins"
      },
      "end_offset": {
        "type": "integer",
        "description": "Character offset where page content ends"
      },
      "primary_node_id": {
        "type": "string",
        "description": "The tree node this page primarily belongs to"
      }
    }
  }
}
```

### 3.4 DetectedTOC Schema (Optional)

```json
{
  "DetectedTOC": {
    "type": "object",
    "properties": {
      "found": {
        "type": "boolean"
      },
      "toc_pages": {
        "type": "array",
        "items": { "type": "integer" },
        "description": "Pages containing the TOC"
      },
      "entries": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "title": { "type": "string" },
            "page_reference": { "type": "string" },
            "matched_node_id": { "type": ["string", "null"] }
          }
        }
      }
    }
  }
}
```

---

## 4. Example Output

### Input Document
A 150-page annual report with chapters, sections, and tables.

### Generated DocumentIndex.json

```json
{
  "schema_version": "1.0.0",
  "document_id": "doc_2024_annual_report_acme",
  "source_file": "ACME_Annual_Report_2024.pdf",
  "title": "ACME Corporation Annual Report 2024",
  "document_type": "report",
  "total_pages": 150,
  "extraction_timestamp": "2026-01-27T14:30:00Z",
  "tree": {
    "node_id": "0001",
    "parent_id": null,
    "title": "ACME Corporation Annual Report 2024",
    "level": 0,
    "start_page": 0,
    "end_page": 149,
    "section_type": "unknown",
    "contains_tables": true,
    "contains_figures": true,
    "docling_element_ids": ["root"],
    "children": [
      {
        "node_id": "0002",
        "parent_id": "0001",
        "title": "Table of Contents",
        "level": 1,
        "start_page": 1,
        "end_page": 2,
        "section_type": "toc",
        "docling_element_ids": ["elem_001", "elem_002"],
        "children": []
      },
      {
        "node_id": "0003",
        "parent_id": "0001",
        "title": "Letter to Shareholders",
        "level": 1,
        "start_page": 3,
        "end_page": 5,
        "section_type": "chapter",
        "summary": "CEO discusses record revenue growth and strategic acquisitions",
        "docling_element_ids": ["elem_003", "elem_004", "elem_005"],
        "children": []
      },
      {
        "node_id": "0004",
        "parent_id": "0001",
        "title": "Financial Highlights",
        "level": 1,
        "start_page": 6,
        "end_page": 45,
        "section_type": "chapter",
        "contains_tables": true,
        "contains_figures": true,
        "docling_element_ids": ["elem_006"],
        "children": [
          {
            "node_id": "0005",
            "parent_id": "0004",
            "title": "Revenue Performance",
            "level": 2,
            "start_page": 6,
            "end_page": 15,
            "section_type": "section",
            "contains_tables": true,
            "docling_element_ids": ["elem_007", "elem_008"],
            "children": [
              {
                "node_id": "0006",
                "parent_id": "0005",
                "title": "Q1-Q4 Revenue Breakdown",
                "level": 3,
                "start_page": 8,
                "end_page": 12,
                "section_type": "subsection",
                "contains_tables": true,
                "docling_element_ids": ["elem_009", "elem_010", "table_001"],
                "children": []
              }
            ]
          },
          {
            "node_id": "0007",
            "parent_id": "0004",
            "title": "Operating Expenses",
            "level": 2,
            "start_page": 16,
            "end_page": 25,
            "section_type": "section",
            "docling_element_ids": ["elem_015"],
            "children": []
          }
        ]
      }
    ]
  },
  "page_boundaries": [
    {
      "page_number": 0,
      "physical_page_label": "i",
      "start_offset": 0,
      "end_offset": 1250,
      "primary_node_id": "0001"
    },
    {
      "page_number": 1,
      "physical_page_label": "ii",
      "start_offset": 1251,
      "end_offset": 3500,
      "primary_node_id": "0002"
    },
    {
      "page_number": 8,
      "physical_page_label": "6",
      "start_offset": 15000,
      "end_offset": 18500,
      "primary_node_id": "0006"
    }
  ],
  "detected_toc": {
    "found": true,
    "toc_pages": [1, 2],
    "entries": [
      {
        "title": "Letter to Shareholders",
        "page_reference": "3",
        "matched_node_id": "0003"
      },
      {
        "title": "Financial Highlights",
        "page_reference": "6",
        "matched_node_id": "0004"
      }
    ]
  }
}
```

---

## 5. Implementation Guidance

### 5.1 Extracting Tree Structure from Docling DOM

Docling already identifies:
- **Section headers** (with hierarchy levels via font size/style)
- **Reading order** (element sequence)
- **Tables and figures** (with captions)
- **Page boundaries** (from PDF structure)

**Pseudocode for Tree Construction**:

```python
def build_document_index(docling_dom: DoclingDocument) -> DocumentIndex:
    """Build hierarchical index from Docling DOM."""

    # 1. Extract all heading elements with their levels
    headings = extract_headings_with_levels(docling_dom)

    # 2. Build tree from headings
    tree = build_tree_from_headings(headings, docling_dom)

    # 3. Assign content ranges to each node
    assign_content_boundaries(tree, docling_dom)

    # 4. Detect and link TOC if present
    toc = detect_table_of_contents(docling_dom)
    if toc:
        link_toc_to_tree(toc, tree)

    # 5. Extract page boundaries
    page_boundaries = extract_page_boundaries(docling_dom)

    # 6. Optionally generate summaries (RAPTOR-style)
    if config.generate_summaries:
        generate_node_summaries(tree)

    return DocumentIndex(
        document_id=docling_dom.document_id,
        title=extract_document_title(docling_dom),
        tree=tree,
        page_boundaries=page_boundaries,
        detected_toc=toc
    )
```

### 5.2 Heading Level Detection

Map Docling's detected heading styles to tree levels:

| Docling Style | Tree Level | Section Type |
|--------------|------------|--------------|
| Title/H1 | 1 | chapter |
| H2 | 2 | section |
| H3 | 3 | subsection |
| H4+ | 4+ | subsection |
| Bold paragraph (context-dependent) | varies | varies |

### 5.3 Handling Edge Cases

**Documents without clear headings**:
- Use page-based segmentation as fallback
- Each N pages becomes a node (configurable, default N=5)
- Set `section_type: "unknown"`

**Very flat documents** (no hierarchy):
- Single root node containing entire document
- Flag for downstream: `"hierarchy_confidence": "low"`

**Multi-column layouts**:
- Reading order from Docling determines section sequence
- Columns don't create separate tree branches

**Tables spanning multiple pages**:
- Table belongs to the node where it starts
- `contains_tables: true` propagates up to parent nodes

---

## 6. Integration Points

### 6.1 Output File Naming

```
{document_id}/
├── normalized.json          # Existing Docling DOM output
├── document_index.json      # NEW: Hierarchical index
└── metadata.json            # Existing metadata
```

### 6.2 Downstream Consumption

**Chunk Stage** will:
1. Read `document_index.json`
2. For each chunk created, add `tree_node_id` field
3. Preserve `start_page`/`end_page` from parent node

**Embed Stage** will:
1. Store `tree_node_id` in vector metadata
2. Store `document_index.json` in document store (for reasoning retrieval)

**Retrieval** will support:
1. **Vector path**: Query → similar chunks → return with tree context
2. **Tree path**: Query → LLM navigates tree → extract full sections

### 6.3 API Contract

```python
class UnifyOutput:
    """Enhanced output from Unify stage."""

    normalized_document: DoclingDocument  # Existing
    document_index: DocumentIndex         # NEW

    def get_node_content(self, node_id: str) -> str:
        """Extract full text content for a tree node."""
        ...

    def get_node_elements(self, node_id: str) -> list[DoclingElement]:
        """Get all Docling DOM elements belonging to a node."""
        ...
```

---

## 7. Validation Requirements

### 7.1 Schema Validation

All `document_index.json` files MUST pass JSON Schema validation.

### 7.2 Consistency Checks

```python
def validate_document_index(index: DocumentIndex, dom: DoclingDocument) -> list[str]:
    errors = []

    # All node_ids must be unique
    node_ids = collect_all_node_ids(index.tree)
    if len(node_ids) != len(set(node_ids)):
        errors.append("Duplicate node_ids detected")

    # Page ranges must not have gaps
    covered_pages = set()
    for node in traverse_tree(index.tree):
        covered_pages.update(range(node.start_page, node.end_page + 1))
    expected_pages = set(range(index.total_pages))
    if covered_pages != expected_pages:
        errors.append(f"Page coverage gap: missing {expected_pages - covered_pages}")

    # All docling_element_ids must exist in DOM
    dom_ids = {elem.id for elem in dom.elements}
    for node in traverse_tree(index.tree):
        for elem_id in node.docling_element_ids:
            if elem_id not in dom_ids:
                errors.append(f"Node {node.node_id} references missing element {elem_id}")

    return errors
```

### 7.3 Test Cases

| Test Case | Input | Expected |
|-----------|-------|----------|
| Simple report | 10-page PDF with 3 chapters | 4 nodes (root + 3 chapters) |
| Nested sections | Document with H1→H2→H3 | 3-level tree |
| No headings | Plain text document | Single root node, low confidence |
| Explicit TOC | Document with TOC on page 2 | `detected_toc.found = true`, entries linked |
| Tables | Document with 5 tables | `contains_tables` flags set appropriately |

---

## 8. Performance Considerations

### 8.1 Processing Overhead

Tree construction from existing Docling DOM should add minimal overhead:
- **Target**: < 100ms per 100-page document
- **Memory**: O(n) where n = number of sections (typically << number of pages)

### 8.2 Output Size

`document_index.json` is typically 1-5% of `normalized.json` size:
- 150-page document: ~10-50KB for index
- Most space is in `docling_element_ids` arrays

### 8.3 Optional Summary Generation

If RAPTOR-style summaries are enabled:
- Adds LLM calls (1 per non-leaf node)
- Consider async/batch processing
- Make configurable: `generate_summaries: bool = False`

---

## 9. Configuration Options

```yaml
# unify_config.yaml
document_index:
  enabled: true

  # Tree construction
  min_heading_level: 1          # Ignore headings below this level
  max_tree_depth: 6             # Maximum nesting depth
  fallback_page_group_size: 5   # Pages per node when no headings

  # Content flags
  detect_tables: true
  detect_figures: true
  detect_equations: true

  # TOC detection
  toc_scan_pages: 20            # First N pages to scan for TOC
  toc_matching_threshold: 0.8   # Fuzzy match threshold for TOC→node linking

  # Summaries (RAPTOR-style)
  generate_summaries: false
  summary_model: "gpt-4o-mini"
  summary_max_tokens: 150

  # Validation
  strict_validation: true       # Fail on validation errors
```

---

## 10. Timeline and Dependencies

### Prerequisites
- [ ] Docling DOM output includes element IDs (verify current implementation)
- [ ] Heading level detection is reliable (may need tuning)
- [ ] Page boundary information is accessible

### Implementation Phases

**Phase 1 (MVP)**: Basic tree + page boundaries
- Tree from headings only
- No summaries
- Basic validation

**Phase 2**: Enhanced detection
- TOC detection and linking
- Content type flags (tables, figures)
- Improved heading detection

**Phase 3**: RAPTOR integration
- Optional summary generation
- Configurable depth for summaries

---

## 11. Questions for Unify Team

1. **Heading Detection**: How reliably does Docling detect heading levels currently? Do we need additional heuristics (font size, bold, etc.)?

2. **Element IDs**: Are Docling DOM elements already assigned stable IDs that persist across processing?

3. **Reading Order**: Is the current reading order detection sufficient for complex multi-column layouts?

4. **TOC Pages**: Is there existing logic to identify TOC pages, or should we implement from scratch?

5. **Performance Budget**: What's the acceptable latency increase per document for this feature?

---

## 12. References

### Research
- [FinanceBench Paper](https://arxiv.org/abs/2311.11944) - Benchmark showing 81% RAG failure rate
- [PageIndex](https://github.com/VectifyAI/PageIndex) - 98.7% accuracy with tree-based retrieval
- [RAPTOR](https://arxiv.org/abs/2401.18059) - Recursive abstractive processing

### Competitive Analysis
- See: `tmp_cleanup/pageindex_competitive_landscape_2025.md`

### Internal Docs
- Foundry Pipeline Architecture: `docs/architecture/diagrams/level-0/`
- Docling Integration: (Unify team documentation)

---

## Contact

**Prepare-Doc Team Lead**: [Your contact]
**Questions**: Slack #foundry-architecture or this document's comments

---

*Document Version: 1.0.0*
*Last Updated: January 27, 2026*
