# ATS Resume Research — Aarohan CareerOS

Retrieved: 2026-06-21

## Purpose
Inform evidence-grounded, ATS-safe resume generation for Aarohan CareerOS. No copyrighted templates were copied.

## Sources

1. [Resumly — ATS Resume Format (2026)](https://www.resumly.ai/resume-format/ats) — Retrieved 2026-06-21
2. [ResumeAdapter — ATS Resume Format 2026](https://www.resumeadapter.com/blog/ats-resume-format-guide-2026) — Retrieved 2026-06-21
3. [ResumeTemplates.com — ATS-Friendly Templates 2026](https://www.resumetemplates.com/ats-friendly-resume-templates/) — Retrieved 2026-06-21
4. [GetNewResume — ATS Resume Format Guide 2026](https://getnewresume.com/blog/ats-resume-format-guide/) — Retrieved 2026-06-21
5. [Resume Optimizer Pro — How to Format a Resume for ATS in 2026](https://resumeoptimizerpro.com/blog/how-to-format-resume-for-ats) — Retrieved 2026-06-21

## Rules applied in Aarohan document generation

| Rule | Implementation |
|------|----------------|
| Single-column layout | DOCX built with sequential paragraphs only |
| Standard headings | Professional Summary, Core Skills, Professional Experience, Education, Certifications |
| Standard fonts | Calibri 11pt body, 14pt section headings |
| No tables/text boxes/icons | python-docx paragraphs and bullet lists only |
| Contact info in body | Name/email/LinkedIn/website at top of document body |
| Reverse-chronological experience | Verified evidence grouped by employment category |
| Keyword mapping | JD keyword extraction mapped to evidence statements |
| Evidence-only claims | Claims without `public_use: true` evidence are excluded with warnings |
| File naming | `{company}_{role}_{profile}_{date}.docx/pdf` |
| Text round-trip check | DOCX text extracted and compared against source sections |
| Page count | Warn if generated resume exceeds 2 pages equivalent (~120 lines) |

## ATS systems referenced in sources

Greenhouse, Lever, Workday, iCIMS, Taleo, BambooHR — public ingestion in this project is limited to approved public ATS feeds per `config/source-policy.yml`.

## Non-goals

- No decorative resume templates
- No graphics, skill bars, or multi-column Canva-style layouts
- No unverified employer names or metrics
