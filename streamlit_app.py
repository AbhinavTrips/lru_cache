"""
🧠 LRU Cache Visualizer — Streamlit App
========================================

Interactive UI that demonstrates how an LRU Cache works with a
simulated SQLite database. Users can look up products by ID and
watch the cache populate, serve hits, and evict LRU entries in
real time.

Run:  streamlit run streamlit_app.py
"""

import streamlit as st
import sqlite3
import time
import random
import pandas as pd
from datetime import datetime

# ────────────────────────────────────────────────
# 1. DATA STRUCTURES — Node & LRU Cache
# ────────────────────────────────────────────────

class Node:
    """Doubly linked list node for the LRU Cache."""

    def __init__(self, key=0, value=0):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """LRU Cache with HashMap + Doubly Linked List (O(1) get/put)."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: dict = {}
        self.head = Node(key="HEAD", value="SENTINEL")
        self.tail = Node(key="TAIL", value="SENTINEL")
        self.head.next = self.tail
        self.tail.prev = self.head

    def _add_node(self, node: Node):
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def _remove_node(self, node: Node):
        node.prev.next = node.next
        node.next.prev = node.prev

    def _move_to_head(self, node: Node):
        self._remove_node(node)
        self._add_node(node)

    def _pop_tail(self) -> Node:
        lru = self.tail.prev
        self._remove_node(lru)
        return lru

    def get(self, key):
        if key in self.cache:
            node = self.cache[key]
            self._move_to_head(node)
            return node.value
        return None

    def put(self, key, value) -> str | None:
        """Returns the evicted key (or None if no eviction)."""
        evicted_key = None
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_head(node)
        else:
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_node(new_node)
            if len(self.cache) > self.capacity:
                evicted = self._pop_tail()
                del self.cache[evicted.key]
                evicted_key = evicted.key
        return evicted_key

    def contents(self) -> list[tuple]:
        """Return cache contents ordered from MRU → LRU."""
        items = []
        current = self.head.next
        while current != self.tail:
            items.append((current.key, current.value))
            current = current.next
        return items

    def clear(self):
        self.cache.clear()
        self.head.next = self.tail
        self.tail.prev = self.head


# ────────────────────────────────────────────────
# 2. DATABASE SETUP
# ────────────────────────────────────────────────

@st.cache_resource
def get_database() -> sqlite3.Connection:
    """Create and populate an in-memory SQLite database (cached across reruns)."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT
        )
    """)
    products = [
        (1, "Wireless Mouse", 29.99, "Electronics", "Ergonomic wireless mouse with USB receiver"),
        (2, "Mechanical Keyboard", 79.99, "Electronics", "RGB backlit mechanical keyboard, blue switches"),
        (3, "USB-C Hub", 45.00, "Electronics", "7-in-1 USB-C hub with HDMI and ethernet"),
        (4, "Monitor Stand", 34.50, "Furniture", "Adjustable aluminum monitor stand"),
        (5, "Desk Lamp", 22.99, "Furniture", "LED desk lamp with 3 brightness levels"),
        (6, "Webcam HD", 59.99, "Electronics", "1080p webcam with built-in microphone"),
        (7, "Notebook A5", 5.99, "Stationery", "Ruled A5 notebook, 200 pages"),
        (8, "Gel Pen Set", 8.49, "Stationery", "Pack of 12 assorted gel pens"),
        (9, "Laptop Sleeve", 19.99, "Accessories", "15-inch neoprene laptop sleeve"),
        (10, "Mouse Pad XL", 14.99, "Accessories", "Extended gaming mouse pad, 900x400mm"),
        (11, "Headphones", 49.99, "Electronics", "Over-ear noise-cancelling headphones"),
        (12, "Phone Charger", 12.99, "Electronics", "Fast-charge USB-C cable, 2m"),
        (13, "Standing Desk Mat", 39.99, "Furniture", "Anti-fatigue standing desk mat"),
        (14, "Cable Organizer", 9.99, "Accessories", "Silicone cable management clips, 10-pack"),
        (15, "Bluetooth Speaker", 35.00, "Electronics", "Portable Bluetooth 5.0 speaker"),
        (16, "Sticky Notes", 3.99, "Stationery", "Neon sticky notes, 6 pads"),
        (17, "Whiteboard Markers", 6.49, "Stationery", "Dry-erase markers, 8 colors"),
        (18, "Ergonomic Chair", 299.99, "Furniture", "Mesh-back ergonomic office chair"),
        (19, "Power Strip", 18.99, "Electronics", "6-outlet surge protector with USB ports"),
        (20, "Screen Cleaner Kit", 7.99, "Accessories", "Microfiber cloth + cleaning spray"),
        (21, "External SSD 1TB", 89.99, "Electronics", "Portable NVMe SSD, USB 3.2"),
        (22, "Wrist Rest", 11.99, "Accessories", "Memory foam keyboard wrist rest"),
        (23, "Desk Organizer", 24.99, "Furniture", "Bamboo desktop organizer with drawers"),
        (24, "Highlighters", 4.99, "Stationery", "Pastel highlighters, 6-pack"),
        (25, "Webcam Light", 15.99, "Electronics", "Ring light clip for video calls"),
    ]
    cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", products)
    conn.commit()
    return conn


DB_LATENCY = 0.3  # Simulated database latency in seconds


def fetch_from_db(conn: sqlite3.Connection, product_id: int) -> dict | None:
    """Fetch a product from the database with simulated latency."""
    time.sleep(DB_LATENCY)
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cur.fetchone()
    return dict(row) if row else None


# ────────────────────────────────────────────────
# 3. SESSION STATE INITIALIZATION
# ────────────────────────────────────────────────

def init_session_state(capacity: int):
    """Initialize or reset session state."""
    if "cache" not in st.session_state or st.session_state.get("cache_capacity") != capacity:
        st.session_state.cache = LRUCache(capacity)
        st.session_state.cache_capacity = capacity
        st.session_state.access_log = []
        st.session_state.hits = 0
        st.session_state.misses = 0
        st.session_state.total_hit_time = 0.0
        st.session_state.total_miss_time = 0.0


def cached_fetch(product_id: int) -> tuple[dict | None, str, float, str | None]:
    """
    Fetch with cache-first strategy.
    Returns: (result, hit_or_miss, elapsed_ms, evicted_key_or_none)
    """
    cache: LRUCache = st.session_state.cache
    db = get_database()
    evicted_key = None

    start = time.time()
    cached_value = cache.get(product_id)
    if cached_value is not None:
        elapsed_ms = (time.time() - start) * 1000
        st.session_state.hits += 1
        st.session_state.total_hit_time += elapsed_ms
        return cached_value, "HIT", elapsed_ms, None

    # Cache miss — go to database
    result = fetch_from_db(db, product_id)
    elapsed_ms = (time.time() - start) * 1000
    st.session_state.misses += 1
    st.session_state.total_miss_time += elapsed_ms

    if result is not None:
        evicted_key = cache.put(product_id, result)

    return result, "MISS", elapsed_ms, evicted_key


# ────────────────────────────────────────────────
# 4. STREAMLIT UI
# ────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="LRU Cache Visualizer",
        page_icon="🧠",
        layout="wide",
    )

    st.title("🧠 LRU Cache Visualizer")
    st.markdown(
        "See how data flows through an **LRU Cache** when accessing a product database. "
        "Cache hits are instant; misses incur a **300ms** simulated database delay."
    )

    # ── Sidebar ──────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Settings")
        capacity = st.slider(
            "Cache Capacity",
            min_value=1,
            max_value=15,
            value=5,
            help="Maximum number of items the cache can hold before evicting the LRU entry.",
        )
        init_session_state(capacity)

        st.divider()

        if st.button("🗑️ Clear Cache & Stats", use_container_width=True):
            st.session_state.cache.clear()
            st.session_state.access_log = []
            st.session_state.hits = 0
            st.session_state.misses = 0
            st.session_state.total_hit_time = 0.0
            st.session_state.total_miss_time = 0.0
            st.rerun()

        st.divider()
        st.subheader("🎲 Bulk Random Access")
        num_random = st.slider("Number of random lookups", 5, 50, 15)
        if st.button("Run Random Lookups", use_container_width=True):
            for _ in range(num_random):
                pid = random.randint(1, 25)
                result, status, elapsed, evicted = cached_fetch(pid)
                name = result["name"] if result else "NOT FOUND"
                st.session_state.access_log.append({
                    "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    "product_id": pid,
                    "product_name": name,
                    "status": status,
                    "time_ms": round(elapsed, 2),
                    "evicted": evicted,
                })
            st.rerun()

        st.divider()
        st.subheader("📖 Available Products")
        db = get_database()
        df_products = pd.read_sql_query("SELECT id, name, price, category FROM products", db)
        st.dataframe(df_products, hide_index=True, use_container_width=True)

    # ── Main area: Lookup ────────────────────────
    col_lookup, col_result = st.columns([1, 2])

    with col_lookup:
        st.subheader("🔍 Product Lookup")
        product_id = st.number_input(
            "Enter Product ID (1-25)",
            min_value=1,
            max_value=25,
            value=1,
            step=1,
        )
        lookup_clicked = st.button("🔎 Fetch Product", use_container_width=True, type="primary")

    with col_result:
        if lookup_clicked:
            result, status, elapsed, evicted = cached_fetch(product_id)

            name = result["name"] if result else "NOT FOUND"
            st.session_state.access_log.append({
                "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "product_id": product_id,
                "product_name": name,
                "status": status,
                "time_ms": round(elapsed, 2),
                "evicted": evicted,
            })

            if status == "HIT":
                st.success(f"✅ **CACHE HIT** — Product {product_id} found in cache! ({elapsed:.1f} ms)")
            else:
                st.warning(f"🔍 **CACHE MISS** — Fetched from database ({elapsed:.1f} ms)")
                if evicted is not None:
                    st.info(f"🗑️ Evicted Product ID **{evicted}** from cache (LRU)")

            if result:
                st.markdown("**Result:**")
                res_df = pd.DataFrame([result])
                st.dataframe(res_df, hide_index=True, use_container_width=True)
            else:
                st.error(f"Product ID {product_id} not found in database.")

    # ── Stats Row ────────────────────────────────
    st.divider()
    total = st.session_state.hits + st.session_state.misses
    hit_rate = (st.session_state.hits / total * 100) if total > 0 else 0
    avg_hit = (st.session_state.total_hit_time / st.session_state.hits) if st.session_state.hits > 0 else 0
    avg_miss = (st.session_state.total_miss_time / st.session_state.misses) if st.session_state.misses > 0 else 0

    st.subheader("📊 Cache Statistics")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Requests", total)
    m2.metric("Cache Hits", st.session_state.hits)
    m3.metric("Cache Misses", st.session_state.misses)
    m4.metric("Hit Rate", f"{hit_rate:.1f}%")
    m5.metric("Cache Size", f"{len(st.session_state.cache.cache)}/{capacity}")

    # Hit vs Miss bar chart
    if total > 0:
        chart_df = pd.DataFrame({
            "Type": ["Hits", "Misses"],
            "Count": [st.session_state.hits, st.session_state.misses],
        })
        st.bar_chart(chart_df.set_index("Type"), color=["#4CAF50"])

    # Average access time comparison
    if st.session_state.hits > 0 and st.session_state.misses > 0:
        st.markdown("**Average Access Time:**")
        tc1, tc2 = st.columns(2)
        tc1.metric("Avg Hit Time", f"{avg_hit:.2f} ms", delta=f"-{avg_miss - avg_hit:.0f} ms faster")
        tc2.metric("Avg Miss Time", f"{avg_miss:.2f} ms")

    # ── Cache Contents ───────────────────────────
    st.divider()
    st.subheader("📋 Current Cache Contents (Most Recent → Least Recent)")

    cache_items = st.session_state.cache.contents()
    if cache_items:
        cache_rows = []
        for pos, (key, val) in enumerate(cache_items, 1):
            label = "🟢 MRU" if pos == 1 else ("🔴 LRU" if pos == len(cache_items) else "")
            row = {"#": pos, "Label": label, "Product ID": key}
            if isinstance(val, dict):
                row.update(val)
            else:
                row["Value"] = val
            cache_rows.append(row)
        st.dataframe(pd.DataFrame(cache_rows), hide_index=True, use_container_width=True)

        # Visual representation of the doubly linked list
        st.markdown("**Doubly Linked List View:**")
        chain = "HEAD ⟷ "
        chain += " ⟷ ".join(
            f"[**{val['name'] if isinstance(val, dict) else val}** (id={key})]"
            for key, val in cache_items
        )
        chain += " ⟷ TAIL"
        st.markdown(chain)
    else:
        st.info("Cache is empty. Look up a product to populate it!")

    # ── Access Log ───────────────────────────────
    st.divider()
    with st.expander("📜 Access Log (click to expand)", expanded=False):
        if st.session_state.access_log:
            log_df = pd.DataFrame(st.session_state.access_log)
            # Color code hit/miss
            def highlight_status(row):
                color = "#d4edda" if row["status"] == "HIT" else "#fff3cd"
                return [f"background-color: {color}"] * len(row)

            styled = log_df.style.apply(highlight_status, axis=1)
            st.dataframe(styled, hide_index=True, use_container_width=True)
        else:
            st.write("No accesses yet.")


if __name__ == "__main__":
    main()
