import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime
from typing import Literal, Optional
import os

try:
    # Import lazy: só será usado se engine=playwright
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except Exception:  # pragma: no cover
    _PLAYWRIGHT_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_g1_headlines(timeout_ms: int = 30000, headless: bool = True, return_df: bool = False, 
                       scroll_attempts: int = 6, wait_after_scroll: int = 3000):
    """Usa Playwright para capturar máximo de conteúdo dinâmico.

    Args:
        timeout_ms: tempo máximo para esperar os seletores.
        headless: executar sem interface gráfica.
        return_df: se True retorna DataFrame.
        scroll_attempts: número de scrolls para carregar mais conteúdo.
        wait_after_scroll: tempo de espera após cada scroll (ms).
    """
    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright não está instalado ou não pôde ser importado.")

    start_time = datetime.now()
    url = "https://g1.globo.com/"
    logging.info(f"[Playwright] Iniciando navegação em {url}")
    rows = []
    seen = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        try:
            # Navegar e aguardar carregamento completo
            page.goto(url, timeout=timeout_ms, wait_until='networkidle')
            logging.info("[Playwright] Página carregada, aguardando elementos dinâmicos...")
            
            # Aguardar primeiro batch de elementos
            page.wait_for_selector('[data-mrf-layout-title]', timeout=timeout_ms)
            
            # Realizar scrolls para carregar mais conteúdo
            for scroll in range(scroll_attempts):
                logging.info(f"[Playwright] Scroll {scroll + 1}/{scroll_attempts}")
                
                # Scroll até o final da página
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                page.wait_for_timeout(wait_after_scroll)
                
                # Aguardar possíveis novos elementos carregarem
                try:
                    page.wait_for_load_state('networkidle', timeout=3000)
                except:
                    pass  # Continua se não houver mais carregamento
            
            # Usar múltiplos seletores para capturar diferentes tipos de elementos
            selectors = [
                '[data-mrf-layout-title]',  # Seletor principal
                '.feed-post-body-title',    # Posts do feed
                '.bstn-hl-title',           # Títulos de headlines
                'h2[data-mrf-layout-title]', # Títulos H2
                'h3[data-mrf-layout-title]', # Títulos H3
                'span[data-mrf-layout-title]', # Spans com título
                'p[data-mrf-layout-title]',    # Parágrafos com título
                '.gui-color-primary[data-mrf-layout-title]' # Elementos com classe específica
            ]
            
            all_elements = []
            
            for selector in selectors:
                try:
                    elements = page.query_selector_all(selector)
                    all_elements.extend(elements)
                    logging.info(f"[Seletor] '{selector}': {len(elements)} elementos")
                except Exception as e:
                    logging.debug(f"[Erro seletor] {selector}: {e}")
                    continue
            
            logging.info(f"[Playwright] Total de elementos encontrados: {len(all_elements)}")
            
            # Processar elementos únicos
            processed_titles = set() 
            
            for el in all_elements:
                try:
                    title = (el.inner_text() or '').strip()
                    
                    # Filtros de qualidade
                    if not title or len(title) < 15:  # Mínimo 15 caracteres
                        continue
                    
                    if title in processed_titles:  # Evitar títulos duplicados
                        continue
                    
                    # Buscar elemento <a> pai
                    anchor = None
                    href = None
                    
                    # Primeira tentativa: elemento pai direto
                    try:
                        anchor_handle = el.evaluate_handle('el => el.closest("a")')
                        if anchor_handle:
                            href = anchor_handle.get_property('href')
                            href_value = href.json_value() if href else None
                            anchor_handle.dispose()
                    except:
                        pass
                    
                    # Segunda tentativa: buscar <a> em elementos filhos
                    if not href_value:
                        try:
                            anchor_in_children = el.query_selector('a')
                            if anchor_in_children:
                                href_value = anchor_in_children.get_attribute('href')
                        except:
                            pass
                    
                    # Terceira tentativa: buscar por data-mrf-link
                    if not href_value:
                        try:
                            parent = el.evaluate_handle('el => el.parentElement')
                            if parent:
                                data_link = parent.get_attribute('data-mrf-link')
                                if data_link:
                                    href_value = data_link
                                parent.dispose()
                        except:
                            pass
                    
                    if not href_value:
                        continue
                    
                    # Normalizar URL
                    if href_value.startswith('/'):
                        href_value = f"https://g1.globo.com{href_value}"
                    elif not href_value.startswith('http'):
                        continue  
                    
                    # Verificar se já foi processado
                    if href_value in seen:
                        continue
                    
                    seen.add(href_value)
                    processed_titles.add(title)
                    
                    rows.append({
                        'title': title,
                        'link': href_value,
                        'source': 'G1',
                        'scraped_at': datetime.now().isoformat()
                    })
                    
                    logging.debug(f"[Coletado] {title[:60]}...")
                        
                except Exception as e:
                    logging.debug(f"[Erro elemento] {str(e)}")
                    continue
        
        except Exception as e:
            logging.error(f"[Playwright] Erro durante navegação: {str(e)}")
        finally:
            browser.close()
    
    duration = (datetime.now() - start_time).total_seconds()
    
    logging.info(f"[Playwright] Concluído em {duration:.1f}s")
    logging.info(f"[Playwright] Total de manchetes únicas coletadas: {len(rows)}")
    
    if not rows:
        logging.warning("[Playwright] Nenhuma manchete foi coletada!")
        return pd.DataFrame() if return_df else None
    
    # Mostrar amostra das primeiras notícias
    logging.info("[Amostra das primeiras manchetes coletadas:]")
    for i, row in enumerate(rows[:5]):
        logging.info(f"  {i+1}. {row['title'][:70]}...")
    
    if return_df:
        return pd.DataFrame(rows)
    
    # Criar diretório de dados se não existir
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'raw')
    os.makedirs(data_dir, exist_ok=True)
    
    # Salvar em CSV na pasta organizada
    timestamp = start_time.strftime('%Y%m%d_%H%M%S')
    filename = f'g1_headlines_{timestamp}.csv'
    filepath = os.path.join(data_dir, filename)
    
    df = pd.DataFrame(rows)
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    
    logging.info(f"[Arquivo salvo] {filepath}")
    
    return rows


def main(engine: Literal['requests','playwright'] = 'playwright'):
    if engine == 'requests':
        # Usando a função principal (agora com Playwright)
        scrape_g1_headlines()
    elif engine == 'playwright':
        scrape_g1_headlines()
    else:
        raise ValueError("Engine inválida. Use 'requests' ou 'playwright'.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Scraper G1')
    parser.add_argument('--engine', choices=['requests','playwright'], default='requests', help='Mecanismo de scraping (default: requests)')
    args = parser.parse_args()
    main(args.engine)