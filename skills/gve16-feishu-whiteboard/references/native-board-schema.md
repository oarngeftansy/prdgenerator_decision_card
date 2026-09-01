# Native board schema

The compiler returns three parts:

- `structure.nodes`: Sections, adjacent rule text, and yellow constraint notes. Safe to write with overwrite.
- `images`: frame ID, project-relative image path, and a token-free image node. Upload each image after structure overwrite and inject the returned media token.
- `overlay.nodes`: red annotations, labels, and native straight connectors. Add incrementally after media upload.

Required native node types: `section`, `image`, `text_shape`, `composite_shape`, and `connector`.

