#!/usr/bin/env python3
"""
Benchmark script for Collision Analytics v2 performance improvements.

Run this to verify the optimizations work correctly and measure speedup.
"""

import sys
import time
from datetime import date
from pathlib import Path
from typing import Dict, List, Set, Any

# Add project to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Mock QGIS classes for standalone testing
class MockField:
    def __init__(self, name: str, is_numeric: bool = False):
        self._name = name
        self._is_numeric = is_numeric
    
    def name(self):
        return self._name
    
    def isNumeric(self):
        return self._is_numeric


class MockFields:
    def __init__(self, fields: List[MockField]):
        self._fields = fields
        self._index = {f.name(): i for i, f in enumerate(fields)}
    
    def indexOf(self, name: str) -> int:
        return self._index.get(name, -1)
    
    def at(self, idx: int):
        return self._fields[idx] if 0 <= idx < len(self._fields) else None
    
    def field(self, name: str):
        idx = self.indexOf(name)
        return self.at(idx) if idx >= 0 else None


class MockFeature:
    def __init__(self, fid: int, attrs: Dict[str, Any]):
        self._fid = fid
        self._attrs = attrs
    
    def id(self):
        return self._fid
    
    def __getitem__(self, key: str):
        return self._attrs.get(key)


class MockQgsFeatureRequest:
    def __init__(self):
        self._fids = None
        self._attrs = None
        self._flags = 0
    
    def setFilterFids(self, fids: List[int]):
        self._fids = set(fids)
        return self
    
    def setSubsetOfAttributes(self, attrs: List[str], fields):
        self._attrs = attrs
        return self
    
    def setFlags(self, flags: int):
        self._flags = flags
        return self


class MockLayer:
    """Mock QgsVectorLayer for testing."""
    
    def __init__(self, name: str, feature_count: int):
        self._name = name
        self._feature_count = feature_count
        self._id = f"mock_layer_{name}_{feature_count}"
        
        # Create mock fields
        self._fields = MockFields([
            MockField("report_date", False),
            MockField("municipality", False),
            MockField("accident_class", True),
            MockField("impact_type", True),
            MockField("light", True),
            MockField("traffic_control", True),
        ])
        
        # Generate synthetic features
        self._features = self._generate_features(feature_count)
    
    def _generate_features(self, count: int) -> List[MockFeature]:
        """Generate synthetic collision data."""
        import random
        random.seed(42)  # Reproducible
        
        municipalities = ["CL", "WH", "OA", "UX", "SC", "AJ", "PI", "BR"]
        accident_classes = ["1", "2", "3", "4"]  # Fatal, Injury, PDO, Unknown
        impact_types = ["1", "2", "3", "4", "5", "99"]
        lights = ["1", "2", "7", "8"]
        traffic_controls = ["1", "2", "3", "10", "99"]
        
        features = []
        base_date = date(2020, 1, 1)
        
        for i in range(count):
            # Spread dates over 10 years
            days_offset = random.randint(0, 3650)
            feat_date = base_date + __import__('datetime').timedelta(days=days_offset)
            
            attrs = {
                "report_date": feat_date.strftime("%Y-%m-%d"),
                "municipality": random.choice(municipalities),
                "accident_class": random.choice(accident_classes),
                "impact_type": random.choice(impact_types),
                "light": random.choice(lights),
                "traffic_control": random.choice(traffic_controls),
            }
            features.append(MockFeature(i, attrs))
        
        return features
    
    def id(self):
        return self._id
    
    def name(self):
        return self._name
    
    def featureCount(self):
        return self._feature_count
    
    def fields(self):
        return self._fields
    
    def getFeatures(self, request=None):
        """Yield features, respecting filter request."""
        if request and request._fids:
            for f in self._features:
                if f.id() in request._fids:
                    yield f
        else:
            yield from self._features
    
    def selectedFeatureIds(self):
        return []


# Mock QgsFeatureRequest flags
class MockQgsFeatureRequestFlags:
    NoGeometry = 1


# Patch for testing - only if QGIS not available
import core.filters as filters_module

if not filters_module.HAS_QGIS:
    filters_module.QgsFeatureRequest = MockQgsFeatureRequest
    filters_module.QgsFeatureRequest.NoGeometry = MockQgsFeatureRequestFlags.NoGeometry

from core.filters import FilterEngine, FilterSpec


def benchmark_filter(
    layer: MockLayer,
    spec: FilterSpec,
    needed_fields: List[str],
    iterations: int = 3
) -> Dict[str, float]:
    """Run filter benchmark."""
    times = []
    results = None
    
    for i in range(iterations):
        engine = FilterEngine(layer)
        start = time.perf_counter()
        results = engine.apply(spec, needed_fields)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    return {
        'min': min(times),
        'max': max(times),
        'avg': sum(times) / len(times),
        'results': results,
    }


def main():
    print("=" * 70)
    print("Collision Analytics v2 - Performance Benchmark")
    print("=" * 70)
    
    # Test scenarios
    scenarios = [
        (50_000, "Small dataset"),
        (250_000, "Target dataset"),
    ]
    
    for feature_count, description in scenarios:
        print(f"\n{'─' * 70}")
        print(f"Scenario: {description} ({feature_count:,} records)")
        print('─' * 70)
        
        # Create mock layer
        layer = MockLayer("test", feature_count)
        
        # Test 1: Date filter only (often most selective)
        print("\n📅 Test 1: Date range filter (2 year window)")
        spec1 = FilterSpec(
            selection_only=False,
            selected_fids=set(),
            date_enabled=True,
            date_field="report_date",
            date_start=date(2021, 1, 1),
            date_end=date(2022, 12, 31),
            category_codes={},
            field_map={
                "date": "report_date",
                "accident_class": "accident_class",
                "municipality": "municipality",
            }
        )
        
        result1 = benchmark_filter(layer, spec1, ["report_date", "accident_class"])
        print(f"   Time: {result1['avg']:.3f}s (min: {result1['min']:.3f}s, max: {result1['max']:.3f}s)")
        print(f"   Matched: {len(result1['results'][0]):,} records")
        
        # Test 2: Single category filter
        print("\n🏷️  Test 2: Single category filter (municipality)")
        spec2 = FilterSpec(
            selection_only=False,
            selected_fids=set(),
            date_enabled=False,
            date_field=None,
            date_start=date(2020, 1, 1),
            date_end=date(2030, 12, 31),
            category_codes={
                "municipality": {"CL", "WH"}  # 2 of 8 municipalities
            },
            field_map={
                "date": "report_date",
                "municipality": "municipality",
            }
        )
        
        result2 = benchmark_filter(layer, spec2, ["report_date", "municipality"])
        print(f"   Time: {result2['avg']:.3f}s (min: {result2['min']:.3f}s, max: {result2['max']:.3f}s)")
        print(f"   Matched: {len(result2['results'][0]):,} records")
        
        # Test 3: Multiple categories (12 filters target)
        print("\n🏷️  Test 3: Multiple category filters (12 concepts)")
        spec3 = FilterSpec(
            selection_only=False,
            selected_fids=set(),
            date_enabled=True,
            date_field="report_date",
            date_start=date(2020, 1, 1),
            date_end=date(2024, 12, 31),
            category_codes={
                "municipality": {"CL", "WH", "OA"},
                "accident_class": {"1", "2"},  # Fatal/Injury only
                "impact_type": {"1", "2", "3"},
                "light": {"7", "8"},  # Dark conditions
                "traffic_control": {"1", "2", "10"},
            },
            field_map={
                "date": "report_date",
                "municipality": "municipality",
                "accident_class": "accident_class",
                "impact_type": "impact_type",
                "light": "light",
                "traffic_control": "traffic_control",
            }
        )
        
        needed3 = ["report_date", "municipality", "accident_class", "impact_type", "light", "traffic_control"]
        result3 = benchmark_filter(layer, spec3, needed3)
        print(f"   Time: {result3['avg']:.3f}s (min: {result3['min']:.3f}s, max: {result3['max']:.3f}s)")
        print(f"   Matched: {len(result3['results'][0]):,} records")
        
        # Test 4: Cache effectiveness
        print("\n💾 Test 4: Cache hit performance")
        engine = FilterEngine(layer)
        
        # First call (cache miss)
        start = time.perf_counter()
        _ = engine.apply(spec3, needed3)
        miss_time = time.perf_counter() - start
        
        # Second call (cache hit)
        start = time.perf_counter()
        cached_result = engine.apply(spec3, needed3)
        hit_time = time.perf_counter() - start
        
        print(f"   Cache miss: {miss_time:.3f}s")
        print(f"   Cache hit:  {hit_time:.3f}s")
        if hit_time > 0:
            print(f"   Speedup:    {miss_time/hit_time:.1f}x")
        
        # Check cache stats
        if engine._cache:
            stats = engine._cache.get_stats()
            print(f"   Cache hits: {stats['hits']}, misses: {stats['misses']}")
            print(f"   Hit rate:   {stats['hit_rate']:.1%}")
    
    print("\n" + "=" * 70)
    print("Benchmark complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
