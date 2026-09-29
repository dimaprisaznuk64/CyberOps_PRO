import { NextResponse } from "next/server";

// `force-dynamic` тут не оптимізація, а умова коректності. Без нього Next
// зберіг би відповідь у статичний бандл під час `next build` — і ми б повернули
// рівно той самий баг, від якого тікаємо: адреса API, вшита в образ, яку
// не можна змінити на власному namespace. Значення має читатися з оточення
// під час РОЗПОДІЛЕННЯ, тобто на кожному запиті.
export const dynamic = "force-dynamic";

/**
 * Публічна адреса API для браузера.
 *
 * Адреса НЕ може бути вшита в бандл: `NEXT_PUBLIC_*` підставляється
 * під час `next build`, тому один і той самий образ на localhost і на
 * сервері з EIP ходив би у `localhost` браузера відвідувача — симптом
 * виглядає як зламаний бекенд, хоча бекенд живий.
 *
 * Значення приходить у змінній `API_PUBLIC_URL`, яку можна перекрити
 * під час розгортання (compose `environment`, k8s ConfigMap). Секретів
 * тут немає: це публічна адреса, браузер і так її бачить.
 */
export function GET(): NextResponse {
  const apiUrl = (process.env.API_PUBLIC_URL ?? "").trim();
  const body = `window.__CYBEROPS__ = ${JSON.stringify({ apiUrl })};\n`;
  return new NextResponse(body, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      // Конфіг змінюється разом із деплоєм; кеш браузера або проксі
      // віддав би стару адресу навіть після правильного розгортання.
      "Cache-Control": "no-store",
    },
  });
}
