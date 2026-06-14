import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_PATH = Path(__file__).parent.parent.parent / "data" / "raw" / "cairo_graph.graphml"


def download_cairo_graph():
    """
    Download the Cairo drive network from OpenStreetMap via osmnx.
    Caches to data/raw/cairo_graph.graphml — subsequent runs skip the download.
    Returns a NetworkX MultiDiGraph.
    """
    import osmnx as ox

    if _CACHE_PATH.exists():
        logger.info("Loading cached Cairo road graph from %s", _CACHE_PATH)
        return ox.load_graphml(_CACHE_PATH)

    logger.info("Downloading Cairo road network from OpenStreetMap (this may take 1-3 minutes)...")
    G = ox.graph_from_place("Cairo, Egypt", network_type="drive")
    nodes, edges = ox.graph_to_gdfs(G)
    logger.info("Downloaded graph: %d nodes, %d edges", len(nodes), len(edges))

    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, _CACHE_PATH)
    logger.info("Cached Cairo graph to %s", _CACHE_PATH)
    return G
