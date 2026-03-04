from __future__ import annotations

from graphlib import TopologicalSorter

from .feature import Feature


class ApplicationServer:
    def __init__(self) -> None:
        self._features: dict[str, Feature] = {}
        self._startup_order: list[str] = []
        self._is_running = False

    @property
    def startup_order(self) -> list[str]:
        return list(self._startup_order)

    def register_feature(self, feature: Feature) -> None:
        if feature.name in self._features:
            raise ValueError(f"feature '{feature.name}' already registered")
        self._features[feature.name] = feature

    def feature(self, name: str) -> Feature:
        return self._features[name]

    def _resolve_order(self) -> list[str]:
        graph: dict[str, set[str]] = {}
        for name, feature in self._features.items():
            graph[name] = set(feature.depends_on)
        for name, deps in graph.items():
            unknown = [dep for dep in deps if dep not in self._features]
            if unknown:
                raise ValueError(f"feature '{name}' depends on unknown {unknown}")
        return list(TopologicalSorter(graph).static_order())

    def boot(self, config: dict | None = None, runtime_context: dict | None = None) -> None:
        cfg = config or {}
        ctx = runtime_context or {}
        order = self._resolve_order()

        for name in order:
            self._features[name].collect_options(cfg)
        for name in order:
            self._features[name].validate_options(cfg)
        for name in order:
            self._features[name].prepare(ctx)
        for name in order:
            self._features[name].start()

        self._startup_order = order
        self._is_running = True

    def shutdown(self) -> None:
        if not self._is_running:
            return
        for name in reversed(self._startup_order):
            self._features[name].begin_shutdown()
        for name in reversed(self._startup_order):
            self._features[name].stop()
        self._is_running = False
