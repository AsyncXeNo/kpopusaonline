from __future__ import annotations

import time
import asyncio

from apify import Actor, Request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        start_urls = actor_input.get('urls')

        if not start_urls:
            Actor.log.info('No start URLs specified in actor input, exiting...')
            await Actor.exit()

        request_queue = await Actor.open_request_queue()

        for start_url in start_urls:
            url = start_url.get('url')
            Actor.log.info(f'Enqueuing {url} ...')
            new_request = Request.from_url(url)
            await request_queue.add_request(new_request)

        Actor.log.info('Launching Chrome WebDriver...')
        chrome_options = ChromeOptions()

        if Actor.config.headless:
            chrome_options.add_argument('--headless')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        driver = webdriver.Chrome(options=chrome_options)

        data = []

        while request := await request_queue.fetch_next_request():
            url = request.url

            Actor.log.info(f'Scraping {url} ...')

            try:
                await asyncio.to_thread(driver.get, url)

                collection = driver.find_elements(By.CSS_SELECTOR, '.woocommerce-breadcrumb a')[-1].get_attribute('innerText').strip()

                title = driver.find_element(By.CSS_SELECTOR, '.product_title').get_attribute('innerText').strip()

                try:
                    price = float(driver.find_element(By.CSS_SELECTOR, '.summary ins .woocommerce-Price-amount').get_attribute('innerText').replace('$', '').replace(',', '').strip())
                except Exception:
                    price = float(driver.find_element(By.CSS_SELECTOR, '.summary .woocommerce-Price-amount').get_attribute('innerText').replace('$', '').replace(',', '').strip())

                try:
                    main_image = driver.find_element(By.CSS_SELECTOR, '.woocommerce-product-gallery__image.flex-active-slide img').get_attribute('src')
                except Exception:
                    main_image = driver.find_element(By.CSS_SELECTOR, '.woocommerce-product-gallery__image img').get_attribute('src')

                image_tags = driver.find_elements(By.CSS_SELECTOR, '.woocommerce-product-gallery__image img')
                images = [image.get_attribute('src') for image in image_tags]

                description = driver.find_element(By.CSS_SELECTOR, '.woocommerce-Tabs-panel--description').get_attribute('innerText').strip()

                description_image_tags = driver.find_elements(By.CSS_SELECTOR, '.woocommerce-Tabs-panel--description img')
                description_images = [image.get_attribute('data-src') for image in description_image_tags]

                try:
                    variant_dropdown = driver.find_element(By.CSS_SELECTOR, '.select2-selection__rendered')
                    variants_exist = True
                except Exception:
                    variants_exist = False

                variant_info = []

                if variants_exist:
                    try:
                        variant_dropdown.click()
                        time.sleep(0.2)
                        options = driver.find_elements(By.CSS_SELECTOR, '.select2-results li')
                        variant_dropdown.click()
                        time.sleep(0.2)

                        for i in range(len(options)):
                            driver.find_element(By.CSS_SELECTOR, '.select2-selection__rendered').click()
                            time.sleep(0.5)
                            option = driver.find_elements(By.CSS_SELECTOR, '.select2-results li')[i]
                            variant_name = option.get_attribute('innerText').strip()
                            option.click()
                            time.sleep(1)

                            try:
                                variant_price = float(driver.find_element(By.CSS_SELECTOR, '.summary ins .woocommerce-Price-amount').get_attribute('innerText').replace('$', '').replace(',', '').strip())
                            except Exception:
                                variant_price = float(driver.find_element(By.CSS_SELECTOR, '.summary .woocommerce-Price-amount').get_attribute('innerText').replace('$', '').replace(',', '').strip())

                            try:
                                variant_image = driver.find_element(By.CSS_SELECTOR, '.woocommerce-product-gallery__image.flex-active-slide img').get_attribute('src')
                            except Exception:
                                variant_image = driver.find_element(By.CSS_SELECTOR, '.woocommerce-product-gallery__image img').get_attribute('src')

                            variant_info.append({
                                'name': variant_name,
                                'price': variant_price,
                                'image': variant_image
                            })
                    except Exception:
                        pass

                data.append({
                    'url': url,
                    'title': title,
                    'collections': [collection],
                    'price': price,
                    'main_image': main_image,
                    'images': images,
                    'description_images': description_images,
                    'description': description,
                    'variants': variant_info
                })

            except Exception:
                Actor.log.exception(f'Cannot extract data from {url}.')

            finally:
                await request_queue.mark_request_as_handled(request)

        driver.quit()

        await Actor.push_data({
            'urls': data
        })