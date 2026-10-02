---
title: "Level 0: Foundry Pipeline Context"
schema_type: common
status: published
owner: core-maintainer
purpose: "Pointer from the diagrams tree to the shared Level 0 pipeline page."
tags:
  - architecture
  - level-0
---

The Level 0 view shows how the five Foundry pipeline repositories link together and where the pipeline ends. The page
is shared word for word by all five repositories, so it lives once in this repository at
[pipeline-level-0.md](../../pipeline-level-0.md) rather than being copied here.

In that diagram this repository is the **Ingest** box (`rag-processor`): the front door and only user-facing service.
It sends documents and images to Prepare-Doc, and audio and video to Prepare-Audio. For the inside of the Ingest box,
see [Level 1](../level-1/index.md).
