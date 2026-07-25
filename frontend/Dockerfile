FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# NEXT_PUBLIC_* vars are inlined into the client JS at build time — without
# this ARG/ENV pair, Railway's frontend service Variable of the same name
# never reaches `npm run build`, no matter what it's set to.
ARG NEXT_PUBLIC_BACKEND_URL
ENV NEXT_PUBLIC_BACKEND_URL=$NEXT_PUBLIC_BACKEND_URL

RUN npm run build

CMD ["npm", "start"]
