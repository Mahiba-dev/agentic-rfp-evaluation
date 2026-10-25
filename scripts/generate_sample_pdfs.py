"""Generate four fictional supplier proposals for the sample RFP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
	PageBreak,
	Paragraph,
	SimpleDocTemplate,
	Spacer,
	Table,
	TableStyle,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_DIR = PROJECT_ROOT / "documents"
RFP_ID = "CVPSC-RFP-2026-014"
PROCUREMENT = "Procurement Evaluation Workspace"
PROCUREMENT_OWNER = "Cedar Valley Public Services Consortium"

INK = colors.HexColor("#17333B")
TEAL = colors.HexColor("#1E746F")
PALE_TEAL = colors.HexColor("#E8F2F0")
PALE_GRAY = colors.HexColor("#F2F5F5")
MID_GRAY = colors.HexColor("#52646A")
GRID = colors.HexColor("#D3DDDE")


@dataclass(frozen=True)
class Proposal:
	name: str
	filename: str
	positioning: str
	executive_summary: str
	understanding: list[str]
	solution: list[str]
	integration_note: str
	implementation: list[tuple[str, str, str]]
	team: list[tuple[str, str, str]]
	price_rows: list[tuple[str, str, str]]
	price_assumptions: list[str]
	security_controls: list[str]
	risks: list[tuple[str, str]]
	support: list[str]
	experience: str
	references: list[tuple[str, str, str]]
	evidence_quality: str
	missing_information: list[str]


PROPOSALS = (
	Proposal(
		name="Apex Systems",
		filename="apex_systems.pdf",
		positioning="Strong technical architecture and security; premium price; moderate 18-week delivery.",
		executive_summary=(
			"Apex Systems proposes a secure, configurable procurement workspace that combines "
			"document intake, evidence-linked AI assistance, human review, and deterministic "
			"Python scoring. The design is technically detailed and security-forward. The bid "
			"is the highest priced of the four and allows a measured 18-week implementation."
		),
		understanding=[
			"CVPSC needs a single auditable workspace for supplier submissions, configurable evaluation criteria, and reviewer decisions.",
			"AI may organize proposal evidence, but weighted scores and supplier rankings must remain reproducible application logic.",
			"Users need role-based access, exportable run records, and clear handling of scanned or incomplete PDFs.",
		],
		solution=[
			"Apex proposes a tenant-isolated web application with a Streamlit reviewer console, Python service layer, and managed PostgreSQL production store; a SQLite-compatible local demonstration mode is included.",
			"PDF text is extracted page by page. An LLM returns schema-constrained criterion assessments with cited proposal evidence; reviewers can inspect each excerpt before deterministic scoring.",
			"The design includes immutable evaluation-run snapshots, configurable criteria, JSON export, and audit events for changes to criteria and reviewer decisions.",
		],
		integration_note="Apex identifies SAML/OIDC single sign-on and an outbound document archive as integration targets. Detailed API field mappings are scheduled for discovery in week 2.",
		implementation=[
			("1. Discovery and architecture", "Confirm workflows, roles, hosting region, data classification", "Weeks 1-3"),
			("2. Core workspace", "Criteria, supplier intake, PDF processing, audit model", "Weeks 4-8"),
			("3. Evaluation and assurance", "Evidence review, deterministic scores, security testing", "Weeks 9-14"),
			("4. Pilot and handover", "UAT, migration rehearsal, training, production release", "Weeks 15-18"),
		],
		team=[
			("Delivery lead", "A. Chen", "0.6 FTE; weekly plan and decisions"),
			("Solution architect", "M. Okafor", "0.5 FTE; architecture and integrations"),
			("Security engineer", "R. Singh", "0.4 FTE; threat model and controls"),
			("Application team", "4 engineers + QA", "Build, test, and pilot support"),
		],
		price_rows=[
			("Discovery and fixed implementation", "$620,000", "One time"),
			("Managed hosting and support", "$148,000", "Per year"),
			("Three-year evaluated total", "$1,064,000", "Implementation + 3 annual terms"),
		],
		price_assumptions=[
			"USD, exclusive of applicable taxes; proposal valid for 90 days.",
			"Includes two production environments, 30 named users, and 1 TB document storage.",
			"External identity-provider fees, OCR for image-only archives, and custom integrations beyond SSO/archive are excluded.",
		],
		security_controls=[
			"TLS 1.2+ in transit, AES-256 at rest, managed key rotation, tenant-scoped authorization, and least-privilege administrative roles.",
			"Proposed controls map to SOC 2 and NIST CSF practices; an independent SOC 2 report is not attached to this sample bid.",
			"Daily encrypted backups, 90-day audit retention, annual penetration testing, and a 24-hour critical-incident notification target.",
		],
		risks=[
			("Identity-provider decisions arrive after week 3", "Could move SSO testing; confirm protocol and test tenant during discovery."),
			("Large scanned archives exceed allowance", "OCR is excluded; sample archive volume before signing and price the option."),
		],
		support=[
			"24x7 P1 intake with a 30-minute acknowledgement target; business-hours P2/P3 support.",
			"Named customer success engineer, monthly service report, quarterly recovery exercise, and 40 hours of administrator training.",
		],
		experience="Apex states that it has delivered three public-sector workflow platforms. The sample bid includes a reference matrix and architecture overview, but no customer artifacts or independently verifiable credentials.",
		references=[
			("Pine County Services (fictional)", "Workflow portal", "Contact available with permission"),
			("Lakeview Transit Cooperative (fictional)", "Document intake", "Reference window: 2024-2025"),
		],
		evidence_quality="Strongest evidence in this set for architecture and stated security controls; certifications and test reports are described but not attached.",
		missing_information=[
			"Confirm production hosting region and data-residency commitment.",
			"Attach current SOC 2 report or equivalent independent assurance evidence.",
			"Confirm retention/deletion period for prompts and model-provider logs.",
		],
	),
	Proposal(
		name="BrightPath Tech",
		filename="brightpath_tech.pdf",
		positioning="Lowest price and fastest 10-week launch; limited experience and weak compliance detail.",
		executive_summary=(
			"BrightPath Tech offers a lean launch of the procurement evaluation workspace in "
			"10 weeks at the lowest proposed price. Its plan emphasizes rapid configuration "
			"and an early pilot. The bid provides limited deployment evidence and leaves several "
			"security, compliance, and support commitments unspecified."
		),
		understanding=[
			"CVPSC wants one place to collect supplier PDFs and compare proposals against a common, editable set of criteria.",
			"The solution should show reviewers the proposal text behind each AI-generated observation.",
			"Scores should be repeatable, with an export for committee review and records retention.",
		],
		solution=[
			"BrightPath proposes a hosted web application using a configurable form builder, a shared document bucket, and a Python scoring service.",
			"The team will use a hosted language-model API to draft criterion notes and evidence snippets for reviewer approval.",
			"The submission describes standard user accounts and encrypted transport; architecture diagrams and data-flow boundaries are not included.",
		],
		integration_note="BrightPath expects to use CSV import/export for the pilot. The bid does not identify an identity-provider connector, API contract, or integration test plan.",
		implementation=[
			("1. Kickoff and templates", "Confirm forms and load starter criteria", "Week 1"),
			("2. Configure workspace", "Supplier upload, reviewer views, basic exports", "Weeks 2-5"),
			("3. Test and adjust", "One sample RFP and two reviewer sessions", "Weeks 6-8"),
			("4. Launch", "Production switch and remote orientation", "Weeks 9-10"),
		],
		team=[
			("Project coordinator", "L. Park", "0.5 FTE; weekly status"),
			("Configuration lead", "D. Evans", "1.0 FTE during setup"),
			("Application engineer", "Shared pool", "On-call build support; allocation not stated"),
		],
		price_rows=[
			("Setup and implementation", "$330,000", "One time"),
			("Cloud service and support", "$62,000", "Per year"),
			("Three-year evaluated total", "$516,000", "Implementation + 3 annual terms"),
		],
		price_assumptions=[
			"USD, exclusive of taxes; introductory price valid for 60 days.",
			"Includes 20 users, 500 GB storage, and standard email support.",
			"Identity federation, migration, OCR, custom reports, and after-hours support are not priced.",
		],
		security_controls=[
			"The bid states that browser traffic is encrypted and that users can be assigned roles.",
			"At-rest encryption, MFA enforcement, tenant isolation, key ownership, audit retention, and hosting region are not specified.",
			"No compliance mapping, incident response target, penetration-test evidence, or independent assurance report is included.",
		],
		risks=[
			("Fast schedule compresses assurance", "Security review is listed as a launch checklist item without an owner or exit criteria."),
			("Uncosted integrations", "CSV-only pilot may require manual work; SSO and API costs are unknown."),
		],
		support=[
			"Email support Monday-Friday, 09:00-17:00 local time; stated initial response target is one business day.",
			"No uptime objective, escalation matrix, recovery-time objective, or included training hours are stated.",
		],
		experience="BrightPath reports one small nonprofit workflow deployment completed in 2025. No production scale, public-sector deployment, or security-assurance experience is documented in this proposal.",
		references=[
			("Harbor Youth Network (fictional)", "Volunteer intake form", "Written reference requested; not attached"),
		],
		evidence_quality="Limited: the proposal includes a feature list and launch estimate but no architecture pack, control evidence, sample reports, or signed references.",
		missing_information=[
			"Provide encryption-at-rest, MFA, hosting-region, backup, and audit-log details.",
			"Identify the assigned engineering team and confirm the 10-week capacity.",
			"Define uptime, incident response, recovery, data deletion, and model-provider terms.",
		],
	),
	Proposal(
		name="NexaWorks",
		filename="nexaworks.pdf",
		positioning="Balanced cost and delivery; strongest implementation plan and support model.",
		executive_summary=(
			"NexaWorks proposes a phased, evidence-first evaluation workspace with clear "
			"acceptance gates, named owners, and a practical transition to operations. Its "
			"implementation and support plans are the most complete in this sample set. "
			"Pricing and delivery are balanced at 16 weeks with a three-year total of $795,000."
		),
		understanding=[
			"CVPSC must be able to adjust evaluation criteria without changing application code and preserve the criteria used for each run.",
			"AI outputs should be traceable to page-level proposal evidence, with missing information called out for reviewers.",
			"Weighted scoring and ranking must remain deterministic, independently testable, and exportable with warnings.",
		],
		solution=[
			"NexaWorks proposes a modular Python application with separate document extraction, evaluation, validation, scoring, ranking, and persistence services.",
			"A reviewer queue supports exception review, reprocessing, and sign-off; run exports contain criteria snapshots, evidence, warnings, and final ranks.",
			"Environments are separated for development, test, and production, with automated deployment checks and a rollback plan.",
		],
		integration_note="SAML/OIDC and a records-export endpoint are addressed in the integration register, with owners, test cases, sample payloads, and acceptance dates assigned during discovery.",
		implementation=[
			("1. Process mapping", "Workflow map, data inventory, acceptance criteria", "Weeks 1-2"),
			("2. Iterative build", "Two-week demos; intake, evidence review, scoring, exports", "Weeks 3-9"),
			("3. Assurance and UAT", "Threat review, accessibility, load test, user acceptance", "Weeks 10-13"),
			("4. Controlled launch", "Pilot, training, operational handover, go-live gate", "Weeks 14-16"),
		],
		team=[
			("Delivery manager", "S. Patel", "0.8 FTE; RAID log and acceptance gates"),
			("Product analyst", "E. Morgan", "0.7 FTE; workflow and test traceability"),
			("Technical lead", "J. Rivera", "1.0 FTE; architecture and code review"),
			("Delivery pod", "2 engineers + QA", "Build, automated tests, and release"),
			("Service lead", "T. Bell", "0.3 FTE; support readiness and transition"),
		],
		price_rows=[
			("Discovery and implementation", "$480,000", "One time"),
			("Hosting, maintenance, and support", "$105,000", "Per year"),
			("Three-year evaluated total", "$795,000", "Implementation + 3 annual terms"),
		],
		price_assumptions=[
			"USD, exclusive of taxes; proposal valid for 90 days.",
			"Includes 30 users, 1 TB storage, two environments, and 80 hours of training.",
			"External identity licensing, historical archive OCR, and work beyond the agreed integration register are change-controlled.",
		],
		security_controls=[
			"TLS 1.2+ in transit, AES-256 at rest, MFA through configured identity provider, least-privilege roles, and encrypted backups.",
			"Audit events are retained for 365 days by default; the retention period is a configurable discovery decision.",
			"Control matrix maps to NIST CSF; a current SOC 2 Type II report is available under NDA but is not attached to this sample.",
		],
		risks=[
			("Criteria change during UAT", "Version each criteria set; require product-owner approval before pilot scoring."),
			("Reference data is incomplete", "Use a discovery data inventory and a masked test set before migration rehearsal."),
		],
		support=[
			"24x7 P1 intake with 30-minute acknowledgement and 4-hour workaround targets; P2 response within 4 business hours.",
			"Named service lead, monthly SLA report, quarterly service review, runbooks, two recovery exercises yearly, and 80 included training hours.",
			"Support handover is an explicit launch gate with owner sign-off and an open-issue threshold.",
		],
		experience="NexaWorks describes five comparable workflow implementations, including two public-sector pilots. Its evidence pack includes a sample RACI, anonymized runbook, release checklist, and acceptance-test traceability matrix.",
		references=[
			("Redwood Water District (fictional)", "Grant review workspace", "Reference available by appointment"),
			("Stonebridge Regional Services (fictional)", "Case intake platform", "Reference available by appointment"),
		],
		evidence_quality="Strongest delivery and support evidence in this set: sample operational artifacts and acceptance traces are identified; independent security evidence remains subject to NDA review.",
		missing_information=[
			"Confirm the production hosting region and approved subprocessors during discovery.",
			"Review the SOC 2 report and model-provider retention terms under NDA before contract signature.",
		],
	),
	Proposal(
		name="Orbit Digital",
		filename="orbit_digital.pdf",
		positioning="Strongest experience and references; medium pricing; integration plan needs detail.",
		executive_summary=(
			"Orbit Digital offers an established delivery team with a strong record of public "
			"sector workflow projects and accessible references. The proposal balances price "
			"and schedule at $720,000 over three years and 13 weeks. Its high-level integration "
			"description needs discovery before delivery commitments can be verified."
		),
		understanding=[
			"CVPSC needs reliable intake and comparison across supplier proposals with reviewer-visible evidence.",
			"The platform must separate AI assistance from deterministic scoring and maintain a defensible audit trail.",
			"The project should transition to CVPSC operations with documented ownership and support routes.",
		],
		solution=[
			"Orbit proposes a managed web portal with configurable evaluation forms, a document library, and a service layer for proposal processing.",
			"The solution will call a hosted LLM for criterion-level evidence summaries and use application code for scoring and ranking.",
			"The proposal emphasizes configurable dashboards and administrative reporting; API boundaries and data synchronization details are not yet defined.",
		],
		integration_note="The bid names SSO, document storage, and the consortium records system as integration points but does not specify protocols, data mappings, owners, test cases, or delivery dates.",
		implementation=[
			("1. Mobilize", "Confirm stakeholders, decision log, and pilot scope", "Weeks 1-2"),
			("2. Configure and build", "Portal, workflow, reporting, and initial integrations", "Weeks 3-7"),
			("3. Validate", "Security checks, user demos, and acceptance testing", "Weeks 8-11"),
			("4. Deploy", "Training, production release, and stabilization", "Weeks 12-13"),
		],
		team=[
			("Engagement director", "P. Dawson", "0.3 FTE; executive escalation"),
			("Project manager", "N. Ali", "0.7 FTE; plan and reporting"),
			("Platform architect", "C. Brooks", "0.4 FTE; design approvals"),
			("Delivery team", "3 engineers + shared QA", "Configuration, integration, and testing"),
		],
		price_rows=[
			("Implementation and configuration", "$435,000", "One time"),
			("Managed hosting and support", "$95,000", "Per year"),
			("Three-year evaluated total", "$720,000", "Implementation + 3 annual terms"),
		],
		price_assumptions=[
			"USD, exclusive of taxes; proposal valid for 90 days.",
			"Includes 25 users, 750 GB storage, and standard business-hours support.",
			"SSO, records-system connector, data migration, and additional storage are included only after scope confirmation; overages may be change requests.",
		],
		security_controls=[
			"Orbit states that data is encrypted in transit and at rest and that administrator actions are logged.",
			"MFA policy, key custody, audit retention duration, hosting region, and independent control evidence are not fully specified.",
			"A risk workshop and penetration test are proposed before launch, but owners and closure thresholds are not attached.",
		],
		risks=[
			("Integration scope remains vague", "Unknown field mappings or connector limits could change schedule and price; baseline interfaces before build."),
			("Security evidence arrives late", "Make control evidence review a pre-production gate with documented exceptions."),
		],
		support=[
			"24x7 P1 hotline with a 1-hour acknowledgement target; business-hours P2/P3 queue.",
			"Named account manager, monthly service review during stabilization, and annual administrator refresher session.",
		],
		experience="Orbit reports 12 years delivering public-sector digital workflow systems and six comparable projects. The proposal provides a detailed reference list and named permission-to-contact status, but no signed performance letters.",
		references=[
			("East Valley Library Network (fictional)", "Grant review portal", "Contact permission confirmed"),
			("North Coast Housing Partnership (fictional)", "Case workflow system", "Contact permission confirmed"),
			("Maple Ridge Utilities Board (fictional)", "Document intake", "Contact permission pending"),
		],
		evidence_quality="Strongest experience evidence in this set: multiple references and named project summaries. Integration and security detail is less specific than the reference material.",
		missing_information=[
			"Provide an interface inventory, API/data mappings, integration owners, and test schedule.",
			"Confirm hosting region, MFA enforcement, key custody, audit retention, and penetration-test closure criteria.",
		],
	),
)


def _styles() -> dict[str, ParagraphStyle]:
	base = getSampleStyleSheet()
	return {
		"title": ParagraphStyle(
			"ProposalTitle", parent=base["Title"], fontName="Helvetica-Bold",
			fontSize=23, leading=26, textColor=INK, alignment=TA_LEFT, spaceAfter=5,
		),
		"subtitle": ParagraphStyle(
			"ProposalSubtitle", parent=base["Normal"], fontName="Helvetica",
			fontSize=9, leading=12, textColor=MID_GRAY, spaceAfter=11,
		),
		"section": ParagraphStyle(
			"Section", parent=base["Heading2"], fontName="Helvetica-Bold",
			fontSize=12, leading=15, textColor=TEAL, spaceBefore=5, spaceAfter=5,
		),
		"body": ParagraphStyle(
			"BodySmall", parent=base["BodyText"], fontName="Helvetica",
			fontSize=8.4, leading=11.2, textColor=INK, spaceAfter=4,
		),
		"bullet": ParagraphStyle(
			"BulletSmall", parent=base["BodyText"], fontName="Helvetica",
			fontSize=8.1, leading=10.4, textColor=INK, leftIndent=10,
			firstLineIndent=-7, spaceAfter=2,
		),
		"table": ParagraphStyle(
			"TableSmall", parent=base["BodyText"], fontName="Helvetica",
			fontSize=7.2, leading=9, textColor=INK,
		),
		"table_header": ParagraphStyle(
			"TableHeader", parent=base["BodyText"], fontName="Helvetica-Bold",
			fontSize=7.2, leading=9, textColor=colors.white,
		),
		"eyebrow": ParagraphStyle(
			"Eyebrow", parent=base["Normal"], fontName="Helvetica-Bold",
			fontSize=8, leading=10, textColor=TEAL, spaceAfter=4,
		),
		"center": ParagraphStyle(
			"Center", parent=base["Normal"], fontName="Helvetica-Bold",
			fontSize=9, leading=12, textColor=INK, alignment=TA_CENTER,
		),
	}


def _safe(value: str) -> str:
	return (
		value.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
	)


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
	return Paragraph(_safe(text), style)


def _bullet_list(items: list[str], style: ParagraphStyle) -> list[Paragraph]:
	return [Paragraph(f"&#8226; {_safe(item)}", style) for item in items]


def _table(
	rows: list[tuple[str, ...]],
	widths: list[float],
	styles: dict[str, ParagraphStyle],
	header: tuple[str, ...] | None = None,
) -> Table:
	content: list[list[Paragraph]] = []
	if header is not None:
		content.append([_paragraph(cell, styles["table_header"]) for cell in header])
	content.extend(
		[[_paragraph(cell, styles["table"]) for cell in row] for row in rows]
	)
	table = Table(content, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
	table.setStyle(
		TableStyle(
			[
				("BACKGROUND", (0, 0), (-1, 0), INK if header else PALE_GRAY),
				("GRID", (0, 0), (-1, -1), 0.4, GRID),
				("VALIGN", (0, 0), (-1, -1), "TOP"),
				("LEFTPADDING", (0, 0), (-1, -1), 5),
				("RIGHTPADDING", (0, 0), (-1, -1), 5),
				("TOPPADDING", (0, 0), (-1, -1), 4),
				("BOTTOMPADDING", (0, 0), (-1, -1), 4),
				("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, PALE_GRAY]),
			]
		)
	)
	return table


def _page_chrome(proposal: Proposal):
	def draw(canvas, doc) -> None:
		canvas.saveState()
		page_width, page_height = letter
		canvas.setStrokeColor(GRID)
		canvas.setLineWidth(0.6)
		canvas.line(0.65 * inch, page_height - 0.45 * inch, page_width - 0.65 * inch, page_height - 0.45 * inch)
		canvas.setFont("Helvetica-Bold", 7.5)
		canvas.setFillColor(TEAL)
		canvas.drawString(0.65 * inch, page_height - 0.34 * inch, PROCUREMENT_OWNER.upper())
		canvas.setFont("Helvetica", 7.5)
		canvas.setFillColor(MID_GRAY)
		canvas.drawRightString(page_width - 0.65 * inch, page_height - 0.34 * inch, RFP_ID)
		canvas.line(0.65 * inch, 0.48 * inch, page_width - 0.65 * inch, 0.48 * inch)
		canvas.setFont("Helvetica", 7)
		canvas.drawString(0.65 * inch, 0.32 * inch, "FICTIONAL SAMPLE PROPOSAL - NOT A REAL BID")
		canvas.drawRightString(page_width - 0.65 * inch, 0.32 * inch, f"{proposal.name}  |  Page {doc.page}")
		canvas.restoreState()
	return draw


def _build_story(proposal: Proposal, styles: dict[str, ParagraphStyle]) -> list[object]:
	story: list[object] = [
		_paragraph("SYNTHETIC SUPPLIER RESPONSE", styles["eyebrow"]),
		_paragraph(proposal.name, styles["title"]),
		_paragraph(f"{PROCUREMENT}  |  RFP {RFP_ID}", styles["subtitle"]),
		_table(
			[
				("Issuing entity", PROCUREMENT_OWNER),
				("Response date", "October 20, 2026"),
				("Offer validity", "90 days unless noted in pricing assumptions"),
				("Bid position", proposal.positioning),
			],
			[1.35 * inch, 5.3 * inch], styles,
		),
		Spacer(1, 7),
		_paragraph("1. Executive Summary", styles["section"]),
		_paragraph(proposal.executive_summary, styles["body"]),
		_paragraph("Understanding of the requirement", styles["section"]),
		*_bullet_list(proposal.understanding, styles["bullet"]),
		_paragraph("2. Proposed Solution", styles["section"]),
		*_bullet_list(proposal.solution, styles["bullet"]),
		_paragraph(f"Integration position: {proposal.integration_note}", styles["body"]),
		PageBreak(),
		_paragraph("3. Implementation Approach", styles["section"]),
		_paragraph(
			"The following work plan is a supplier estimate for the shared RFP scope. "
			"Milestones require CVPSC product-owner review and written acceptance.",
			styles["body"],
		),
		_table(
			proposal.implementation,
			[1.42 * inch, 3.75 * inch, 1.48 * inch], styles,
			header=("Phase", "Milestone and deliverable", "Target"),
		),
		Spacer(1, 8),
		_paragraph("Timeline and acceptance gates", styles["section"]),
		_table(
			[
				("Design sign-off", "Requirements traceability, role map, and integration assumptions approved."),
				("Build complete", "Core flows demonstrated with synthetic supplier proposals."),
				("Pilot exit", "Security and UAT issues dispositioned; results reviewed by CVPSC."),
				("Go-live", "Support owner accepts runbooks, recovery plan, and escalation path."),
			],
			[1.5 * inch, 5.15 * inch], styles,
			header=("Gate", "Evidence required for acceptance"),
		),
		Spacer(1, 8),
		_paragraph("Proposed team structure", styles["section"]),
		_table(
			proposal.team,
			[1.28 * inch, 1.28 * inch, 4.09 * inch], styles,
			header=("Role", "Named lead", "Allocation and responsibility"),
		),
		PageBreak(),
		_paragraph("4. Price and Commercial Assumptions", styles["section"]),
		_table(
			proposal.price_rows,
			[3.0 * inch, 1.3 * inch, 2.35 * inch], styles,
			header=("Price component", "Amount", "Basis"),
		),
		Spacer(1, 4),
		*_bullet_list(proposal.price_assumptions, styles["bullet"]),
		_paragraph("5. Security, Compliance, and Risk Controls", styles["section"]),
		*_bullet_list(proposal.security_controls, styles["bullet"]),
		_table(
			proposal.risks,
			[1.75 * inch, 4.9 * inch], styles,
			header=("Risk", "Proposed control or open action"),
		),
		_paragraph("6. Support, Experience, and References", styles["section"]),
		*_bullet_list(proposal.support, styles["bullet"]),
		_paragraph(proposal.experience, styles["body"]),
		_table(
			proposal.references,
			[2.5 * inch, 2.15 * inch, 2.0 * inch], styles,
			header=("Fictional reference", "Relevant work", "Availability"),
		),
		Spacer(1, 3),
		_paragraph(f"Evidence quality: {proposal.evidence_quality}", styles["body"]),
		_paragraph("Open items and missing information", styles["section"]),
		*_bullet_list(proposal.missing_information, styles["bullet"]),
	]
	return story


def generate_sample_pdfs(output_dir: Path = DOCUMENTS_DIR) -> list[Path]:
	"""Write all four fictional three-page PDFs and verify their page counts."""
	output_dir.mkdir(parents=True, exist_ok=True)
	styles = _styles()
	generated: list[Path] = []
	for proposal in PROPOSALS:
		path = output_dir / proposal.filename
		doc = SimpleDocTemplate(
			str(path),
			pagesize=letter,
			rightMargin=0.65 * inch,
			leftMargin=0.65 * inch,
			topMargin=0.68 * inch,
			bottomMargin=0.65 * inch,
			title=f"{proposal.name} - {PROCUREMENT} - {RFP_ID}",
			author=proposal.name,
			subject="Fictional synthetic supplier proposal for model evaluation testing",
		)
		doc.build(_build_story(proposal, styles), onFirstPage=_page_chrome(proposal), onLaterPages=_page_chrome(proposal))
		reader = PdfReader(str(path), strict=True)
		if len(reader.pages) != 3:
			raise RuntimeError(
				f"Generated {path.name} with {len(reader.pages)} pages; expected exactly 3."
			)
		generated.append(path)
	return generated


def main() -> None:
	for path in generate_sample_pdfs():
		print(f"Generated {path}")


if __name__ == "__main__":
	main()
