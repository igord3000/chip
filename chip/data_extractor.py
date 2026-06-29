"""Universal data extractor - works with HTML, JSON, text, etc."""
import re
import json
from typing import Optional
from dataclasses import dataclass


@dataclass
class ExtractedData:
    """Structured data extracted from any source."""
    source_type: str  # html, json, text, api
    raw_data: str
    structured: dict
    summary: str
    
    def to_dict(self) -> dict:
        return {
            "source_type": self.source_type,
            "structured": self.structured,
            "summary": self.summary
        }


class DataExtractor:
    """Universal extractor for different data sources."""
    
    def extract(self, data: str, source_type: str = "auto", context: str = "") -> ExtractedData:
        """Extract data from any source."""
        
        # Auto-detect source type
        if source_type == "auto":
            source_type = self._detect_type(data)
        
        # Extract based on type
        if source_type == "json":
            return self._extract_json(data, context)
        elif source_type == "html":
            return self._extract_html(data, context)
        else:
            return self._extract_text(data, context)
    
    def _detect_type(self, data: str) -> str:
        """Detect data source type."""
        stripped = data.strip()
        
        # Check for JSON (more flexible)
        if stripped.startswith('{') or stripped.startswith('['):
            try:
                json.loads(stripped)
                return "json"
            except json.JSONDecodeError:
                # Check if it looks like JSON even if invalid
                if ':' in stripped and ('{' in stripped or '[' in stripped):
                    return "json"
        
        # Check for HTML
        if '<html' in stripped.lower() or '<div' in stripped.lower() or '<p>' in stripped.lower():
            return "html"
        
        return "text"
    
    def _extract_json(self, data: str, context: str = "") -> ExtractedData:
        """Extract data from JSON."""
        try:
            parsed = json.loads(data)
            structured = self._flatten_json(parsed)
            summary = self._summarize_structured(structured, context)
            
            return ExtractedData(
                source_type="json",
                raw_data=data[:500],
                structured=structured,
                summary=summary
            )
        except json.JSONDecodeError:
            return self._extract_text(data, context)
    
    def _extract_html(self, data: str, context: str = "") -> ExtractedData:
        """Extract data from HTML."""
        # Remove scripts and styles
        text = re.sub(r'<script[^>]*>.*?</script>', '', data, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        
        # Decode HTML entities
        import html as html_module
        text = html_module.unescape(text)
        
        # Remove tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return self._extract_text(text, context)
    
    def _extract_text(self, data: str, context: str = "") -> ExtractedData:
        """Extract data from plain text."""
        structured = {
            "text": data[:2000],
            "length": len(data)
        }
        
        # Try to extract structured data
        structured.update(self._extract_patterns(data, context))
        
        summary = self._generate_summary(structured, context)
        
        return ExtractedData(
            source_type="text",
            raw_data=data[:500],
            structured=structured,
            summary=summary
        )
    
    def _extract_patterns(self, text: str, context: str = "") -> dict:
        """Extract common patterns from text."""
        patterns = {}
        
        # Numbers
        numbers = re.findall(r'(\d+[,.]?\d*)\s*(°C|°F|мм|гПа|hPa|км/ч|м/с|%)', text)
        if numbers:
            patterns["measurements"] = [
                {"value": n, "unit": u} for n, u in numbers[:10]
            ]
        
        # URLs
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
        if urls:
            patterns["urls"] = urls[:5]
        
        # Dates
        dates = re.findall(r'\d{1,2}[./-]\d{1,2}[./-]\d{2,4}', text)
        if dates:
            patterns["dates"] = dates[:5]
        
        # Emails
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        if emails:
            patterns["emails"] = emails[:5]
        
        # Key-value pairs (common in weather, APIs)
        kv_patterns = re.findall(r'(\w+[\s:]*)[:=]\s*([^\n,;]+)', text)
        if kv_patterns:
            patterns["key_values"] = {k.strip(): v.strip() for k, v in kv_patterns[:10]}
        
        return patterns
    
    def _flatten_json(self, data: any, prefix: str = "") -> dict:
        """Flatten nested JSON to key-value pairs."""
        result = {}
        
        if isinstance(data, dict):
            for key, value in data.items():
                new_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, (dict, list)):
                    result.update(self._flatten_json(value, new_key))
                else:
                    result[new_key] = value
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_key = f"{prefix}[{i}]"
                if isinstance(item, (dict, list)):
                    result.update(self._flatten_json(item, new_key))
                else:
                    result[new_key] = item
        
        return result
    
    def _summarize_structured(self, data: dict, context: str = "") -> str:
        """Generate summary from structured data."""
        lines = []
        
        for key, value in list(data.items())[:20]:
            if isinstance(value, (str, int, float, bool)):
                lines.append(f"• {key}: {value}")
            elif isinstance(value, list):
                lines.append(f"• {key}: {len(value)} items")
        
        return "\n".join(lines) if lines else "No structured data found"
    
    def _generate_summary(self, data: dict, context: str = "") -> str:
        """Generate human-readable summary."""
        parts = []
        
        if "text" in data:
            text = data["text"][:500]
            parts.append(text)
        
        if "measurements" in data:
            parts.append("\nMeasurements:")
            for m in data["measurements"]:
                parts.append(f"  • {m['value']} {m['unit']}")
        
        if "urls" in data:
            parts.append(f"\nURLs: {len(data['urls'])} found")
        
        return "\n".join(parts) if parts else "Data extracted"
    
    def format_for_display(self, extracted: ExtractedData) -> str:
        """Format extracted data for display."""
        lines = []
        
        # Source type
        lines.append(f"Source: {extracted.source_type}")
        lines.append("")
        
        # Structured data
        if extracted.structured:
            lines.append("Structured data:")
            for key, value in extracted.structured.items():
                if isinstance(value, list):
                    lines.append(f"  {key}: {len(value)} items")
                elif isinstance(value, dict):
                    lines.append(f"  {key}: {len(value)} fields")
                else:
                    lines.append(f"  {key}: {str(value)[:100]}")
        
        # Summary
        if extracted.summary:
            lines.append("")
            lines.append("Summary:")
            lines.append(extracted.summary)
        
        return "\n".join(lines)
