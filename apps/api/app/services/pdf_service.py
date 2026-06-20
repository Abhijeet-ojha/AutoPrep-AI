"""PDF report generation service."""

from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
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


class PDFReportGenerator:
    """Generate professional PDF reports for datasets."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()
    
    def _add_custom_styles(self):
        """Add custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=1,  # Center
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2563eb'),
            spaceBefore=20,
            spaceAfter=12,
        ))

    
    def generate_report(
        self,
        dataset_id: str,
        file_name: str,
        profile: dict[str, Any],
        audit: dict[str, Any],
        health: dict[str, Any],
        recommendations: list[dict[str, Any]],
        cleaning_history: list[dict[str, Any]],
        feature_engineering: list[dict[str, Any]],
        ml_readiness: dict[str, Any],
        executive_summary: str | None = None,
    ) -> bytes:
        """
        Generate complete PDF report.
        
        Returns:
            PDF bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        story = []
        
        # Title page
        story.extend(self._build_title_page(dataset_id, file_name))
        story.append(PageBreak())
        
        # Executive summary
        if executive_summary:
            story.extend(self._build_executive_summary(executive_summary))
            story.append(PageBreak())
        
        # Dataset overview
        story.extend(self._build_overview(profile))
        story.append(Spacer(1, 0.2 * inch))
        
        # Health score
        story.extend(self._build_health_score(health))
        story.append(Spacer(1, 0.2 * inch))
        
        # Quality findings
        story.extend(self._build_quality_findings(audit))
        story.append(PageBreak())
        
        # Cleaning actions
        story.extend(self._build_cleaning_actions(recommendations, cleaning_history))
        story.append(Spacer(1, 0.2 * inch))
        
        # Feature engineering
        story.extend(self._build_feature_engineering(feature_engineering))
        story.append(PageBreak())
        
        # ML readiness
        story.extend(self._build_ml_readiness(ml_readiness))
        
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes

    
    def _build_title_page(self, dataset_id: str, file_name: str) -> list:
        """Build title page."""
        elements = []
        
        elements.append(Spacer(1, 2 * inch))
        elements.append(Paragraph("AutoPrep AI", self.styles['CustomTitle']))
        elements.append(Paragraph("Dataset Analysis Report", self.styles['Heading2']))
        elements.append(Spacer(1, 0.5 * inch))
        
        elements.append(Paragraph(f"<b>Dataset:</b> {file_name}", self.styles['Normal']))
        elements.append(Paragraph(f"<b>Report ID:</b> {dataset_id}", self.styles['Normal']))
        elements.append(Paragraph(
            f"<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            self.styles['Normal']
        ))
        
        return elements
    
    def _build_executive_summary(self, summary: str) -> list:
        """Build executive summary section."""
        elements = []
        
        elements.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph(summary, self.styles['Normal']))
        
        return elements
    
    def _build_overview(self, profile: dict[str, Any]) -> list:
        """Build dataset overview section."""
        elements = []
        
        elements.append(Paragraph("1. Dataset Overview", self.styles['SectionHeader']))
        
        summary = profile['summary']
        data = [
            ['Metric', 'Value'],
            ['Total Rows', f"{summary['rows']:,}"],
            ['Total Columns', f"{summary['columns']:,}"],
            ['Memory Usage', f"{summary['memory_usage_bytes'] / (1024*1024):.2f} MB"],
        ]
        
        table = Table(data, colWidths=[3 * inch, 3 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(table)
        
        return elements

    
    def _build_health_score(self, health: dict[str, Any]) -> list:
        """Build health score section."""
        elements = []
        
        elements.append(Paragraph("2. Dataset Health Score", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.1 * inch))
        
        score = health['score']
        color = colors.green if score >= 80 else colors.orange if score >= 60 else colors.red
        
        elements.append(Paragraph(
            f"<font color='{color.hexval()}' size='20'><b>{score}/100</b></font>",
            self.styles['Normal']
        ))
        elements.append(Spacer(1, 0.1 * inch))
        
        # Breakdown
        breakdown = health['breakdown']
        data = [['Category', 'Score']]
        for category, score_val in breakdown.items():
            data.append([category, f"{score_val}/25"])
        
        table = Table(data, colWidths=[3 * inch, 2 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(table)
        
        # Suggestions
        if health.get('improvement_suggestions'):
            elements.append(Spacer(1, 0.1 * inch))
            elements.append(Paragraph("<b>Improvement Suggestions:</b>", self.styles['Normal']))
            for suggestion in health['improvement_suggestions']:
                elements.append(Paragraph(f"• {suggestion}", self.styles['Normal']))
        
        return elements

    
    def _build_quality_findings(self, audit: dict[str, Any]) -> list:
        """Build quality findings section."""
        elements = []
        
        elements.append(Paragraph("3. Quality Findings", self.styles['SectionHeader']))
        
        # Missing values
        elements.append(Paragraph("<b>Missing Values:</b>", self.styles['Heading3']))
        total_missing = sum(audit['missing']['by_column'].values())
        elements.append(Paragraph(f"Total missing cells: {total_missing:,}", self.styles['Normal']))
        elements.append(Paragraph(
            f"Rows with missing values: {audit['missing']['rows_with_missing']:,}",
            self.styles['Normal']
        ))
        
        # Duplicates
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph("<b>Duplicate Records:</b>", self.styles['Heading3']))
        elements.append(Paragraph(
            f"Duplicate rows found: {audit['duplicates']['duplicate_rows']:,}",
            self.styles['Normal']
        ))
        
        # Outliers
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph("<b>Outliers:</b>", self.styles['Heading3']))
        total_outliers = sum(audit['outliers']['iqr'].values())
        elements.append(Paragraph(f"Total outliers detected (IQR method): {total_outliers:,}", self.styles['Normal']))
        
        return elements
    
    def _build_cleaning_actions(
        self,
        recommendations: list[dict[str, Any]],
        history: list[dict[str, Any]]
    ) -> list:
        """Build cleaning actions section."""
        elements = []
        
        elements.append(Paragraph("4. Cleaning Actions", self.styles['SectionHeader']))
        
        elements.append(Paragraph(
            f"<b>Recommendations:</b> {len(recommendations)} actions suggested",
            self.styles['Normal']
        ))
        elements.append(Paragraph(
            f"<b>Actions Performed:</b> {len(history)} operations completed",
            self.styles['Normal']
        ))
        
        return elements
    
    def _build_feature_engineering(self, suggestions: list[dict[str, Any]]) -> list:
        """Build feature engineering section."""
        elements = []
        
        elements.append(Paragraph("5. Feature Engineering Suggestions", self.styles['SectionHeader']))
        elements.append(Paragraph(f"{len(suggestions)} transformations recommended", self.styles['Normal']))
        
        return elements
    
    def _build_ml_readiness(self, ml_readiness: dict[str, Any]) -> list:
        """Build ML readiness section."""
        elements = []
        
        elements.append(Paragraph("6. ML Readiness Assessment", self.styles['SectionHeader']))
        
        score = ml_readiness['score']
        elements.append(Paragraph(f"<b>ML Readiness Score:</b> {score}/100", self.styles['Normal']))
        elements.append(Spacer(1, 0.1 * inch))
        
        elements.append(Paragraph(ml_readiness.get('reasoning', ''), self.styles['Normal']))
        
        return elements


# Global instance
pdf_generator = PDFReportGenerator()
