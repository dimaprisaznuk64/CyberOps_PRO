FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# NEXT_PUBLIC_API_URL — лише для локальної розробки (npm run dev) і для
# образів, зібраних із явним build-arg. Тут БЕЗ дефолту: `ENV X=${ARG:-...}`
# підставляв би http://localhost:8000 в бандл, і кожен стенд, зібраний без
# .env (CI, kind), мав би UI, який ходить у localhost браузера. Публічна
# адреса приходить у рантаймі через /runtime-config.js (див. API_PUBLIC_URL).
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/package.json /app/package-lock.json ./
COPY --from=build /app/next.config.mjs ./
COPY --from=build /app/.next ./.next
COPY --from=build /app/src ./src
RUN npm ci --omit=dev
EXPOSE 3000
CMD ["npm", "run", "start"]