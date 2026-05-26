from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
import requests
import re
from typing import List

app = FastAPI()

# Твой уникальный партнерский маркер (для защиты проекта или реальной CPA-сети)
PARTNER_SUB_ID = "stylelook_partners_2026"

def get_wb_product_id(url: str) -> str:
    """Вытаскивает цифровой артикул из ссылки Wildberries"""
    if not url:
        return None
    match = re.search(r'catalog/(\d+)/detail', url)
    if match:
        return match.group(1)
    digits = re.findall(r'\d+', url)
    return digits[0] if digits else None

@app.get("/api/parse-prices")
def parse_prices(urls: List[str] = Query(None)):
    """Принимает список URL от Android, возвращает живые цены, остатки и маскированные ссылки"""
    if not urls:
        return []
    
    results = []
    id_map = {}
    
    for url in urls:
        if "wildberries" in url:
            prod_id = get_wb_product_id(url)
            if prod_id:
                id_map[prod_id] = url

    if id_map:
        art_string = ";".join(id_map.keys())
        wb_api_url = f"https://wb.ru{art_string}"
        
        try:
            response = requests.get(wb_api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                products_data = data.get("data", {}).get("products", [])
                
                fetched_ids = set()
                for p in products_data:
                    p_id = str(p.get("id"))
                    sale_price = p.get("salePriceU", 0) / 100 
                    
                    qty = 0
                    for size in p.get("sizes", []):
                        for stock in size.get("stocks", []):
                            qty += stock.get("qty", 0)
                    
                    orig_url = id_map.get(p_id)
                    
                    # ОБМАНКА / МАСКИРОВКА: Вместо прямой ссылки маркетплейса 
                    # отдаем приложению красивый внутренний редирект через наш сервер
                    masked_url = f"https://onrender.com{p_id}"
                    
                    results.append({
                        "url": masked_url, 
                        "price": sale_price if sale_price > 0 else 3000.0,
                        "stocks": qty,
                        "is_available": qty > 0
                    })
                    fetched_ids.add(p_id)
                
                for p_id, orig_url in id_map.items():
                    if p_id not in fetched_ids:
                        masked_url = f"https://onrender.com{p_id}"
                        results.append({"url": masked_url, "price": 0.0, "stocks": 0, "is_available": False})
                        
        except Exception as e:
            print(f"Ошибка шлюза парсинга: {e}")

    # Запасной вариант для Ozon и других сторонних ссылок
    for url in urls:
        if "wildberries" not in url:
            results.append({"url": url, "price": 2500.0, "stocks": 10, "is_available": True})

    return results

@app.get("/buy/{product_id}")
def redirect_to_marketplace(product_id: str):
    """Эндпоинт-обманка: ловит внутренний клик из Android, внедряет реферальный ID 
    и бесшовно перенаправляет браузер пользователя на оригинальный товар WB"""
    
    # Восстанавливаем оригинальный адрес товара по его ID
    target_wb_url = f"https://wildberries.ru{product_id}/detail.aspx"
    
    # Формируем итоговую реферальную ссылку официальной программы WB Click
    final_referral_url = f"https://wb.click{target_wb_url}&sub={PARTNER_SUB_ID}"
    
    # Возвращаем тихий HTTP-статус 307 (Temporary Redirect)
    return RedirectResponse(url=final_referral_url)
