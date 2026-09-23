"""
Marketplace (TikTok Shop & Shopee Open API) Semantic Integrator for System 1.
"""
import os
import sys
import json
from engine import System1ContinuousEngine

MEMORY_PATH = "/root/.gemini/antigravity-cli/system1_global/memory.json"

MARKETPLACE_PATTERNS = {
    "FEATURE_IMPLEMENTATION": [
        "tiktok shop api",
        "shopee open api",
        "shopee api v2",
        "tiktok partner api",
        "tiktok partner center",
        "tiktok order fulfillment",
        "tiktok webhook",
        "shopee push mechanism",
        "v2.order.get_order_detail",
        "v2.order.get_order_list",
        "v2.logistics.ship_order",
        "v2.product.get_item_list",
        "v2.product.add_item",
        "v2.product.update_stock",
        "v2.returns.get_return_detail",
        "shopee oauth token refresh",
        "tiktok oauth access_token",
        "tiktok sync product catalog",
        "tiktok return refund api",
        "shopee order tracking push",
        "tiktok shipping label generator",
        "shopee shipping document parameter"
    ],
    "DATABASE_SCHEMA_MIGRATION": [
        "tabela shopee_orders",
        "tabela tiktok_orders",
        "tabela marketplace_tokens",
        "tabela shopee_webhook_events",
        "tabela tiktok_fulfillment_logs",
        "tabela marketplace_products_mapping",
        "tabela shopee_logistics_channels"
    ],
    "TOOL_EXECUTION_COMMAND": [
        "gerar shopee sign",
        "calcular hmac sha256 tiktok",
        "sync shopee orders",
        "sync tiktokshop webhook",
        "testar webhook shopee",
        "testar webhook tiktok partner",
        "curl partner.shopeemobile.com",
        "curl api.tiktokshop.com"
    ],
    "CODE_BUGFIX": [
        "shopee invalid signature",
        "tiktok signature mismatch",
        "shopee token expired error",
        "tiktok access_token expirado",
        "tiktok webhook timeout 3s",
        "shopee error_not_found",
        "shopee rate limit exceeded"
    ],
    "ARCHITECTURE_DESIGN": [
        "arquitetura multi-marketplace",
        "integracao tiktok shop e shopee",
        "hub de integracao e-commerce",
        "shopee webhook listener architecture",
        "tiktok shop idempotency handler"
    ],
    "TEST_AUTOMATION": [
        "teste shopee sandbox api",
        "teste tiktok partner mock",
        "teste shopee signature hmac",
        "teste webhook idempotency tiktok"
    ]
}

def integrate_marketplace_knowledge():
    print("[*] Integrando semântica de TikTok Shop e Shopee Open API...")
    engine = System1ContinuousEngine(memory_path=MEMORY_PATH)
    patterns = engine.memory.setdefault("patterns", {})
    
    total_added = 0
    for category, terms in MARKETPLACE_PATTERNS.items():
        existing = set(patterns.get(category, []))
        new_terms = [t for t in terms if t and t not in existing]
        patterns.setdefault(category, []).extend(new_terms)
        total_added += len(new_terms)
        print(f" [+] {category}: +{len(new_terms)} termos adicionados (Total: {len(patterns[category])})")

    engine._save()
    print(f"\n[✓] {total_added} novos padrões de TikTok Shop e Shopee integrados com sucesso ao System 1!")

if __name__ == "__main__":
    integrate_marketplace_knowledge()
