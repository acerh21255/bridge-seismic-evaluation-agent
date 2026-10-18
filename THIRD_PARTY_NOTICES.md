# Third-party dependencies and references

The application uses LangChain create_agent and LangGraph as installed dependencies, not a copied/reimplemented agent loop.

- LangChain: https://github.com/langchain-ai/langchain (MIT)
- LangGraph: https://github.com/langchain-ai/langgraph (MIT)
- langchain-openai and langgraph-checkpoint-sqlite: installed distribution metadata and license files remain authoritative.
- python-docx (MIT) and lxml (BSD-3-Clause): Word document generation.
- jsonschema (MIT): handoff contract validation.
- matplotlib (PSF-based Matplotlib License): design spectrum and ground-motion spectrum charts.
- pypdfium2 (Apache-2.0 / BSD-3-Clause, bundles PDFium): PDF page previews.
- Pillow (MIT-CMU / HPND): image handling for previews and HTML output.
- Microsoft Word (optional, user-installed): refreshes the table of contents and exports PDF through COM automation. Not redistributed.
- Exact tested package versions: requirements.lock.txt.

Research and design references (not copied into the application distribution):
- Datawhale Hello-Agents: https://github.com/datawhalechina/hello-agents at 5caceca4e4c9a3d25cd14627881436953f4d6912.
- HelloAgents SDK: https://github.com/jjyaoao/helloagents, inspected pyproject.toml declares CC-BY-NC-SA-4.0. Used for comparison only.
- Bojie Li ai-agent-book: https://github.com/bojieli/ai-agent-book at 04c88c53df962eb4375a0fad9ec041066529b358, repository root Apache-2.0 with possible subproject notices. Used for design reference only.

The reference reports in templates/reference and the report master template derived from them retain their existing ownership. The golden handoff package and its figures are extracted from the 76K278+308 and 53K271+730 reference reports for format and workflow verification only. This project does not grant new redistribution rights to those materials. The bundle is a project development handoff.
