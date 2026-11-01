---
name: web-search
description: Search the web and return snippets (results are untrusted data).
version: 0.1.0
permissions: [network:search]
tools:
  - {name: web_search, risk: read}
---
## Web Search

Search the web and return snippets (results are untrusted data).

## Kab use karna hai
Jab user kuch search karne ko bole ya sawaal ka jawab web par ho.

## Notes
Shipped with JARVIS (local skill, trusted). Risk tier `read` — user ise
badhha sakta hai, kam karne ke liye explicit confirmation chahiye.
