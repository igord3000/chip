"""Test data extractor with various data sources."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from chip.data_extractor import DataExtractor


def test_html_extraction():
    """Test HTML data extraction."""
    extractor = DataExtractor()
    
    html = """
    <html>
    <body>
        <h1>Weather in Miass</h1>
        <p>Temperature: +13°C</p>
        <p>Humidity: 70%</p>
        <p>Wind: 2.4 m/s</p>
    </body>
    </html>
    """
    
    result = extractor.extract(html)
    print(f"Source type: {result.source_type}")
    print(f"Structured: {result.structured}")
    print()
    return result


def test_json_extraction():
    """Test JSON data extraction."""
    extractor = DataExtractor()
    
    json_data = """
    {
        "current_condition": {
            "temp_C": "13",
            "humidity": "70",
            "windspeedKmph": "2.4",
            "weatherDesc": [{"value": "Partly cloudy"}]
        },
        "weather": [
            {"date": "2025-06-30", "maxtempC": "18", "mintempC": "12"}
        ]
    }
    """
    
    result = extractor.extract(json_data)
    print(f"Source type: {result.source_type}")
    print(f"Structured: {result.structured}")
    print()
    return result


def test_text_extraction():
    """Test text data extraction."""
    extractor = DataExtractor()
    
    text = """
    Погода в Миассе: температура +13°C, влажность 70%, ветер 2.4 м/с.
    Давление 722 мм рт. ст. Облачно с прояснениями.
    """
    
    result = extractor.extract(text)
    print(f"Source type: {result.source_type}")
    print(f"Structured: {result.structured}")
    print()
    return result


def test_auto_detect():
    """Test auto-detection of source type."""
    extractor = DataExtractor()
    
    sources = [
        ("{'key': 'value'}", "json"),
        ("<html><body>test</body></html>", "html"),
        ("Just plain text", "text"),
    ]
    
    for data, expected in sources:
        detected = extractor._detect_type(data)
        status = "✓" if detected == expected else "✗"
        print(f"{status} '{data[:30]}...' -> {detected} (expected: {expected})")
    
    print()


def test_format_for_display():
    """Test display formatting."""
    extractor = DataExtractor()
    
    result = extractor.extract("Temperature: +13°C, Humidity: 70%")
    formatted = extractor.format_for_display(result)
    print("Formatted output:")
    print(formatted)
    print()


def run_all_tests():
    """Run all data extractor tests."""
    print("=" * 60)
    print("Data Extractor Tests")
    print("=" * 60)
    
    print("\n1. HTML extraction:")
    test_html_extraction()
    
    print("2. JSON extraction:")
    test_json_extraction()
    
    print("3. Text extraction:")
    test_text_extraction()
    
    print("4. Auto-detection:")
    test_auto_detect()
    
    print("5. Display formatting:")
    test_format_for_display()
    
    print("=" * 60)
    print("All tests completed!")


if __name__ == "__main__":
    run_all_tests()
