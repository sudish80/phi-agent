"""Shopping Assistant — AI-powered product discovery, comparison, and purchase assistance.
Integrates SQLite product DB, FAISS policy search, semantic routing, and LLM agents.
Adapted from ShoppingGPT (github.com/Hoanganhvu123/ShoppingGPT) architecture.
"""

import json
import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent / "shopping_data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
PRODUCT_DB_PATH = _DATA_DIR / "products.db"
POLICY_PATH = _DATA_DIR / "policies.txt"
FAISS_INDEX_DIR = _DATA_DIR / "faiss_index"

# ---------------------------------------------------------------------------
# Sample product utterances for semantic routing
# ---------------------------------------------------------------------------
PRODUCT_UTTERANCES = [
    "how much does this dress cost", "what colors are available for this shirt",
    "is this pair of jeans in stock", "what clothing items do you have",
    "can you show me some shoes", "do you have any discounts on winter coats",
    "what's the warranty on this jacket", "do you offer free shipping",
    "can I return this sweater if it doesn't fit", "what's your best-selling item",
    "do you have eco-friendly options", "are these t-shirts made locally",
    "what's the material of this blouse", "do you have this in a larger size",
    "are these shoes suitable for running", "what's your return policy",
    "can you recommend a good winter jacket", "do you have sales on summer dresses",
    "what's the price range for formal wear", "do you have any waterproof jackets",
    "can you help me find a dress for a wedding", "do you offer gift cards",
    "do you have any vegan leather options", "what accessories go with this outfit",
]

CHITCHAT_UTTERANCES = [
    "do you like watching movies", "what's your favorite food",
    "how's the weather", "do you have any hobbies",
    "what's your opinion on artificial intelligence", "tell me a joke",
    "what's your favorite book", "do you believe in aliens",
    "what's the meaning of life", "do you have any pets",
    "what's your favorite music genre", "how was your day",
    "what's your favorite season", "what's your idea of a perfect day",
    "what's your favorite type of cuisine", "do you have any phobias",
    "what's your favorite sport", "do you prefer mountains or beaches",
    "what's your favorite way to relax", "what's your favorite ice cream flavor",
]

# ---------------------------------------------------------------------------
# SQLite Product Database
# ---------------------------------------------------------------------------
PRODUCT_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    product_code TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    material TEXT DEFAULT '',
    size TEXT DEFAULT '',
    color TEXT DEFAULT '',
    brand TEXT DEFAULT '',
    gender TEXT DEFAULT 'unisex',
    stock_quantity INTEGER DEFAULT 0,
    price REAL DEFAULT 0.0,
    category TEXT DEFAULT '',
    description TEXT DEFAULT '',
    rating REAL DEFAULT 0.0
);
"""

_SAMPLE_PRODUCTS = [
    ("P001", "Classic Cotton T-Shirt", "100% Organic Cotton", "S,M,L,XL", "White,Black,Navy,Red", "EcoWear", "unisex", 150, 29.99, "tops", "Soft organic cotton tee with reinforced stitching", 4.5),
    ("P002", "Slim Fit Jeans", "Denim (98% Cotton, 2% Elastane)", "28,30,32,34,36", "Blue,Black,Grey", "DenimCo", "male", 80, 79.99, "bottoms", "Modern slim fit with slight stretch for comfort", 4.2),
    ("P003", "Wool Blend Blazer", "70% Wool, 30% Polyester", "38,40,42,44,46", "Charcoal,Navy,Brown", "FormalEdge", "male", 45, 189.99, "outerwear", "Two-button blazer with satin lining", 4.7),
    ("P004", "Floral Summer Dress", "Viscose (100%)", "XS,S,M,L,XL", "Blue Floral,Pink Floral,White", "SummerBloom", "female", 60, 59.99, "dresses", "Lightweight floral print with adjustable waist tie", 4.4),
    ("P005", "Leather Crossbody Bag", "Genuine Leather", "One Size", "Black,Brown,Tan", "LuxeCarry", "female", 35, 149.99, "accessories", "Premium leather with adjustable strap and multiple pockets", 4.8),
    ("P006", "Running Shoes Pro", "Mesh/Synthetic", "7,8,9,10,11,12", "Black/Red,Blue/White,All Black", "SpeedFit", "unisex", 120, 129.99, "footwear", "Lightweight running shoes with responsive cushioning", 4.6),
    ("P007", "Cashmere Crew Neck Sweater", "100% Cashmere", "S,M,L,XL", "Camel,Grey,Black,Burgundy", "LuxeKnit", "unisex", 30, 199.99, "tops", "Ultra-soft cashmere with ribbed cuffs and hem", 4.9),
    ("P008", "Waterproof Rain Jacket", "Nylon with PU Coating", "S,M,L,XL,XXL", "Yellow,Green,Blue,Black", "WeatherPro", "unisex", 90, 89.99, "outerwear", "Fully waterproof with sealed seams and adjustable hood", 4.3),
    ("P009", "Silk Evening Gown", "100% Silk", "2,4,6,8,10,12", "Midnight Blue,Emerald,Red", "HauteCouture", "female", 15, 499.99, "dresses", "Floor-length silk gown with beaded bodice", 4.9),
    ("P010", "Organic Linen Shirt", "100% Linen", "S,M,L,XL", "White,Blue,Pink,Striped", "EcoWear", "unisex", 100, 69.99, "tops", "Breathable linen shirt perfect for summer", 4.1),
    ("P011", "Leather Chelsea Boots", "Full-Grain Leather", "7,8,9,10,11,12,13", "Brown,Black,Tan", "BootMaster", "male", 55, 179.99, "footwear", "Classic Chelsea boot with elastic side panels", 4.5),
    ("P012", "Wool Winter Scarf", "100% Merino Wool", "One Size", "Grey,Burgundy,Navy,Camel", "WinterWarm", "unisex", 200, 49.99, "accessories", "Extra-long merino wool scarf with fringe details", 4.3),
    ("P013", "Sports Leggings", "75% Nylon, 25% Spandex", "XS,S,M,L,XL", "Black,Grey,Teal,Maroon", "FlexFit", "female", 140, 54.99, "bottoms", "High-waist compression leggings with pocket", 4.4),
    ("P014", "Denim Jacket", "100% Cotton Denim", "S,M,L,XL,XXL", "Light Blue,Dark Blue,Black", "DenimCo", "unisex", 65, 89.99, "outerwear", "Classic denim jacket with button closure", 4.2),
    ("P015", "Silk Tie Collection", "100% Silk", "One Size", "Various Patterns", "FormalEdge", "male", 80, 39.99, "accessories", "Set of 3 silk ties with different patterns", 4.0),
]

# ---------------------------------------------------------------------------
# Sample store policies
# ---------------------------------------------------------------------------
_SAMPLE_POLICIES = """
RETURN POLICY
You may return unused items within 30 days of delivery for a full refund.
Items must be in original condition with all tags attached.
Sale items are final sale and cannot be returned.
Refunds are processed within 5-7 business days after we receive the return.

SHIPPING POLICY
Free standard shipping on orders over $75.
Standard shipping: 5-7 business days ($5.99)
Express shipping: 2-3 business days ($12.99)
Next-day shipping: 1 business day ($24.99)
International shipping available to 30+ countries (rates vary).

WARRANTY INFORMATION
All clothing items come with a 90-day warranty against manufacturing defects.
Footwear has a 6-month warranty against sole separation and material defects.
Premium items (over $150) include a 1-year extended warranty.
Warranty does not cover normal wear and tear, misuse, or unauthorized alterations.

SIZE AND FIT
Free size exchanges within 30 days.
Visit any store for professional fitting assistance.
Size guides are available on every product page.
Custom alterations available for an additional fee.

SUSTAINABILITY
We use 100% recyclable packaging materials.
Our organic cotton line is GOTS certified.
We partner with carbon-neutral shipping providers.
For every item sold, we plant one tree through OneTreePlanted.

GIFT SERVICES
Free gift wrapping available for all items.
Gift receipts included by default.
E-gift cards available from $25 to $500.
Personalized gift messages can be added at checkout.
"""


def _init_database():
    """Initialize the product database with schema and sample data."""
    try:
        conn = sqlite3.connect(str(PRODUCT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute(PRODUCT_SCHEMA)
        count = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            cursor.executemany(
                "INSERT OR REPLACE INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                _SAMPLE_PRODUCTS
            )
            conn.commit()
            logger.info(f"Initialized product DB with {len(_SAMPLE_PRODUCTS)} products")
        else:
            logger.info(f"Product DB already has {count} products")
        conn.close()
    except Exception as e:
        logger.error(f"Failed to init product database: {e}")

def _init_policies():
    """Write sample policies file if not exists."""
    if not POLICY_PATH.exists():
        POLICY_PATH.write_text(_SAMPLE_POLICIES, encoding="utf-8")
        logger.info("Created sample policies file")


class ProductDataLoader:
    """Context manager for SQLite product queries with SQL injection prevention."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(PRODUCT_DB_PATH)
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def search(self, query: str = "", **filters) -> List[Dict]:
        """Search products with case-insensitive partial matching and filters."""
        if not self.conn:
            self.connect()
        sql = "SELECT * FROM products WHERE 1=1"
        params = []
        if query:
            sql += " AND (LOWER(product_name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(category) LIKE ? OR LOWER(brand) LIKE ?)"
            like = f"%{query.lower()}%"
            params.extend([like, like, like, like])
        for key, val in filters.items():
            if val is not None and hasattr(val, "__iter__") and not isinstance(val, str):
                placeholders = ",".join("?" for _ in val)
                sql += f" AND {key} IN ({placeholders})"
                params.extend(val)
            elif val is not None:
                sql += f" AND {key} = ?"
                params.append(val)
        if "price_min" in filters:
            sql = sql.replace("AND price_min = ?", "AND price >= ?")
        if "price_max" in filters:
            sql = sql.replace("AND price_max = ?", "AND price <= ?")
        sql += " ORDER BY product_name LIMIT 50"
        cursor = self.conn.execute(sql, params)
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def get_by_code(self, code: str) -> Optional[Dict]:
        if not self.conn:
            self.connect()
        cursor = self.conn.execute("SELECT * FROM products WHERE product_code = ?", (code,))
        row = cursor.fetchone()
        if row:
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))
        return None

    def get_categories(self) -> List[str]:
        if not self.conn:
            self.connect()
        rows = self.conn.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
        return [r[0] for r in rows if r[0]]

    def get_brands(self) -> List[str]:
        if not self.conn:
            self.connect()
        rows = self.conn.execute("SELECT DISTINCT brand FROM products ORDER BY brand").fetchall()
        return [r[0] for r in rows if r[0]]


# ---------------------------------------------------------------------------
# FAISS-based Policy Search
# ---------------------------------------------------------------------------
class PolicySearch:
    """Vector search over store policies using FAISS."""

    def __init__(self):
        self._vectorstore = None

    def _get_embeddings(self):
        try:
            from sentence_transformers import SentenceTransformer
            return SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            return None

    def _load_or_create(self):
        if self._vectorstore is not None:
            return self._vectorstore
        embeddings = self._get_embeddings()
        if embeddings is None:
            return None
        try:
            from langchain_community.vectorstores import FAISS
            from langchain_community.document_loaders import TextLoader
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            if FAISS_INDEX_DIR.exists() and (FAISS_INDEX_DIR / "index.faiss").exists():
                self._vectorstore = FAISS.load_local(
                    str(FAISS_INDEX_DIR), embeddings,
                    allow_dangerous_deserialization=True
                )
            else:
                _init_policies()
                loader = TextLoader(str(POLICY_PATH), encoding="utf-8")
                docs = loader.load()
                splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
                chunks = splitter.split_documents(docs)
                self._vectorstore = FAISS.from_documents(chunks, embeddings)
                FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
                self._vectorstore.save_local(str(FAISS_INDEX_DIR))
        except ImportError:
            return None
        return self._vectorstore

    def search(self, query: str, k: int = 5) -> List[str]:
        vs = self._load_or_create()
        if vs is None:
            return self._keyword_fallback(query)
        try:
            results = vs.similarity_search(query, k=k)
            return [doc.page_content for doc in results]
        except Exception:
            return self._keyword_fallback(query)

    def _keyword_fallback(self, query: str) -> List[str]:
        """Simple keyword policy search when FAISS is unavailable."""
        _init_policies()
        text = POLICY_PATH.read_text(encoding="utf-8")
        sections = re.split(r"\n{2,}(?=[A-Z ]+\n)", text)
        query_lower = query.lower()
        matched = []
        for sec in sections:
            if query_lower in sec.lower():
                matched.append(sec.strip())
        return matched[:5] or [text.strip()[:500]]


# ---------------------------------------------------------------------------
# Semantic Router (lightweight TF-IDF based)
# ---------------------------------------------------------------------------
class SemanticRouter:
    """Lightweight semantic router using TF-IDF cosine similarity."""

    def __init__(self):
        self._vectorizer = None
        self._route_embeddings = {}
        self._init_routes()

    def _init_routes(self):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            import numpy as np
            all_texts = PRODUCT_UTTERANCES + CHITCHAT_UTTERANCES
            self._vectorizer = TfidfVectorizer(stop_words="english")
            self._vectorizer.fit(all_texts)
            self._route_embeddings["product"] = self._vectorizer.transform(PRODUCT_UTTERANCES).mean(axis=0).A1
            self._route_embeddings["chitchat"] = self._vectorizer.transform(CHITCHAT_UTTERANCES).mean(axis=0).A1
        except ImportError:
            self._vectorizer = None

    def guide(self, query: str) -> str:
        if self._vectorizer is None:
            return self._keyword_route(query)
        import numpy as np
        q_vec = self._vectorizer.transform([query]).toarray()[0]
        scores = {}
        for route, emb in self._route_embeddings.items():
            dot = np.dot(q_vec, emb)
            norm = np.linalg.norm(q_vec) * np.linalg.norm(emb)
            scores[route] = dot / norm if norm > 0 else 0
        best = max(scores, key=scores.get)
        return best if scores[best] > 0.1 else "chitchat"

    def _keyword_route(self, query: str) -> str:
        q = query.lower()
        product_kw = ["buy", "price", "cost", "shirt", "jeans", "dress", "shoe", "bag",
                      "size", "color", "warranty", "return", "shipping", "order",
                      "product", "stock", "sale", "discount", "recommend", "jacket",
                      "sweater", "pant", "boot", "hat", "scarf", "accessory"]
        if any(kw in q for kw in product_kw):
            return "product"
        return "chitchat"


# ---------------------------------------------------------------------------
# Core shopping tools
# ---------------------------------------------------------------------------

async def search_products(
    query: str,
    category: str = "",
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    brand: str = "",
    features: str = "",
    sort_by: str = "relevance",
) -> str:
    """Search for products matching natural language criteria. Uses SQLite product DB + LLM enrichment."""
    from backend.shared.llm_client import llm_client
    from backend.orchestrator.agent import agent

    _init_database()
    results = []
    try:
        with ProductDataLoader() as loader:
            filters = {}
            if category: filters["category"] = category
            if brand: filters["brand"] = brand
            db_results = loader.search(query, **filters)
            if min_price is not None:
                db_results = [r for r in db_results if float(r.get("price", 0)) >= min_price]
            if max_price is not None:
                db_results = [r for r in db_results if float(r.get("price", 0)) <= max_price]
            results = db_results[:20]
    except Exception as e:
        logger.warning(f"Product DB search failed: {e}")

    web_context = ""
    if not results:
        try:
            web_context = await agent.tools.execute("search_web", {
                "query": f"buy {query} best price review"
            })
        except Exception:
            pass

    if results:
        products_json = json.dumps([
            {k: v for k, v in r.items() if k != "product_code"} for r in results
        ], indent=2, default=str)
        system_prompt = (
            "You are a helpful shopping assistant with access to product inventory. "
            "Recommend products based on the user's needs. Format recommendations clearly."
        )
        user_msg = f"""Customer request: {query}

Available products in our inventory:
{products_json}

Filters: Category={category or 'Any'} Price={'$'+str(min_price)+'-$'+str(max_price) if min_price or max_price else 'Any'} Brand={brand or 'Any'}

Provide:
1. **Top Picks** matching their needs
2. **Comparison** of key options
3. **Recommendation** with reasoning"""
    else:
        system_prompt = "You are a helpful shopping assistant."
        user_msg = f"""Customer request: {query}

Web search results:
{web_context[:2000] if web_context else 'No product info available'}

Provide product recommendations, prices, and shopping advice."""

    result = await llm_client.generate([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ])
    return result.content if hasattr(result, "content") else str(result)


async def compare_products(
    product_a: str,
    product_b: str,
    criteria: str = "price, features, quality, value",
) -> str:
    """Compare two products side-by-side using product DB + LLM analysis."""
    from backend.shared.llm_client import llm_client
    _init_database()

    product_info = {}
    for name in [product_a, product_b]:
        with ProductDataLoader() as loader:
            results = loader.search(name)
            if results:
                product_info[name] = results[0]
            else:
                product_info[name] = {"product_name": name}

    context = json.dumps(product_info, indent=2, default=str)
    result = await llm_client.generate([
        {"role": "system", "content": "You are an objective product comparison expert."},
        {"role": "user", "content": f"""Compare these two products:

Product Data:
{context}

Comparison criteria: {criteria}

Provide: side-by-side specs comparison, pros/cons, price comparison, value assessment, recommendations per use case."""},
    ])
    return result.content if hasattr(result, "content") else str(result)


async def get_shopping_list(category: str, budget: float, preferences: str = "") -> str:
    """Generate a curated shopping list with budget allocation using product DB."""
    from backend.shared.llm_client import llm_client
    _init_database()

    inventory = ""
    with ProductDataLoader() as loader:
        items = loader.search(category) if category else loader.search("")
        if items:
            inventory = json.dumps([
                {"name": i["product_name"], "price": i["price"],
                 "category": i["category"], "brand": i["brand"]}
                for i in items[:30]
            ], indent=2)

    result = await llm_client.generate([
        {"role": "system", "content": "You are a personal shopping advisor."},
        {"role": "user", "content": f"""Create a curated shopping list:

Category: {category}
Budget: ${budget}
Preferences: {preferences or 'General'}

Available inventory:
{inventory or 'No specific inventory data'}

For each item include: name, estimated price, why recommended, priority (must-have/nice-to-have), budget allocation %."""},
    ])
    return result.content if hasattr(result, "content") else str(result)


async def product_search_db(query: str) -> str:
    """Search products in the local SQLite database by name, category, or brand."""
    _init_database()
    try:
        with ProductDataLoader() as loader:
            results = loader.search(query)
            if not results:
                cats = loader.get_categories()
                brands = loader.get_brands()
                return json.dumps({
                    "count": 0,
                    "query": query,
                    "categories_available": cats,
                    "brands_available": brands,
                    "suggestion": "Try a broader search term or browse by category"
                }, indent=2)
            return json.dumps({"count": len(results), "results": results[:20]}, indent=2, default=str)
    except Exception as e:
        return f"Error searching products: {e}"


async def product_get_details(product_code: str) -> str:
    """Get full details for a specific product by code."""
    _init_database()
    try:
        with ProductDataLoader() as loader:
            product = loader.get_by_code(product_code.upper())
            if product:
                return json.dumps(product, indent=2, default=str)
            return f"No product found with code: {product_code}"
    except Exception as e:
        return f"Error: {e}"


async def product_list_categories() -> str:
    """List all available product categories in the store."""
    _init_database()
    try:
        with ProductDataLoader() as loader:
            cats = loader.get_categories()
            brands = loader.get_brands()
            return json.dumps({"categories": cats, "brands": brands}, indent=2)
    except Exception as e:
        return f"Error: {e}"


async def policy_search(query: str) -> str:
    """Search store policies (returns, shipping, warranty, etc.) using vector search."""
    _init_policies()
    try:
        ps = PolicySearch()
        results = ps.search(query, k=5)
        if not results:
            return "No policy information found for your query."
        return "\n\n---\n\n".join(results)
    except Exception as e:
        return f"Policy search error: {e}"


async def shopping_route_query(query: str) -> str:
    """Classify a user query as product-related or general chat."""
    try:
        router = SemanticRouter()
        route = router.guide(query)
        return json.dumps({"route": route, "query": query}, indent=2)
    except Exception as e:
        return json.dumps({"route": "chitchat", "query": query, "error": str(e)})


async def get_product_recommendations(preferences: str, budget: Optional[float] = None) -> str:
    """Get AI-powered product recommendations based on user preferences."""
    from backend.shared.llm_client import llm_client
    _init_database()

    with ProductDataLoader() as loader:
        inventory = loader.search("")
        inventory_json = json.dumps([
            {"name": p["product_name"], "price": p["price"],
             "category": p["category"], "brand": p["brand"],
             "material": p["material"], "rating": p["rating"]}
            for p in inventory[:50]
        ], indent=2, default=str)

    result = await llm_client.generate([
        {"role": "system", "content": "You are a personal stylist and shopping consultant."},
        {"role": "user", "content": f"""Customer preferences: {preferences}
Budget: {'$'+str(budget) if budget else 'No limit'}

Our current inventory:
{inventory_json}

Recommend the best 3-5 products from our inventory that match the customer's needs.
For each: why it's a good fit, key features, value assessment."""},
    ])
    return result.content if hasattr(result, "content") else str(result)


async def check_store_policy(policy_type: str) -> str:
    """Look up a specific store policy by type (returns, shipping, warranty, etc.)."""
    _init_policies()
    ps = PolicySearch()
    results = ps.search(policy_type, k=3)
    if results:
        return "\n\n".join(results)
    return f"No policy found for '{policy_type}'. Available policies include: Returns, Shipping, Warranty, Size & Fit, Sustainability, Gift Services."


async def track_order_status(order_id: str) -> str:
    """Track the status of an order (simulated)."""
    return json.dumps({
        "order_id": order_id,
        "status": "processing" if order_id.startswith("ORD") else "shipped",
        "estimated_delivery": "5-7 business days",
        "carrier": "FedEx",
        "tracking_number": f"FX{order_id[-6:] if len(order_id) >= 6 else '123456'}",
        "message": f"Order {order_id} is currently being processed and will ship within 1-2 business days."
    }, indent=2)
