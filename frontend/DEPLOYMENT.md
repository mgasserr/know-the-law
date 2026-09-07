# Deployment Guide

## Deployment Options

### Option 1: Vercel (Recommended)

Vercel is the easiest way to deploy Vite + React applications.

#### Steps:

1. **Connect repository:**
   - Sign up at [vercel.com](https://vercel.com)
   - Import your Git repository

2. **Configure:**
   - Framework: Vite
   - Build command: `npm run build`
   - Output directory: `dist`

3. **Environment variables:**
   - Add `REACT_APP_API_URL` pointing to your production backend

4. **Deploy:**
   - Click "Deploy"
   - URL will be provided

### Option 2: Netlify

#### Steps:

1. **Connect repository:**
   - Sign up at [netlify.com](https://netlify.com)
   - Connect your Git repository

2. **Configure build settings:**
   ```
   Build command: npm run build
   Publish directory: dist
   ```

3. **Environment variables:**
   - Add in Netlify Dashboard → Site settings → Build & deploy → Environment
   - Set `REACT_APP_API_URL`

4. **Deploy:**
   - Automatic on push to main branch

### Option 3: Docker

Create a production-ready Docker image:

#### Dockerfile:

```dockerfile
# Build stage
FROM node:18-alpine as builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM node:18-alpine

WORKDIR /app

# Install serve to run the production build
RUN npm install -g serve

COPY --from=builder /app/dist ./dist

EXPOSE 3000

# Set environment variables
ENV REACT_APP_API_URL=http://localhost:8000

CMD ["serve", "-s", "dist", "-l", "3000"]
```

#### Build and run:

```bash
# Build image
docker build -t legal-chatbot-frontend:1.0.0 .

# Run container
docker run -p 3000:3000 \
  -e REACT_APP_API_URL=https://api.example.com \
  legal-chatbot-frontend:1.0.0
```

### Option 4: AWS S3 + CloudFront

#### Steps:

1. **Build the application:**
   ```bash
   npm run build
   ```

2. **Create S3 bucket:**
   - Enable static website hosting
   - Set index.html as index document
   - Set error.html as error document

3. **Upload build files:**
   ```bash
   aws s3 sync dist/ s3://your-bucket-name/
   ```

4. **Create CloudFront distribution:**
   - Origin: S3 bucket
   - Default root object: index.html

5. **Configure routing:**
   - Point error pages to index.html (for SPA routing)

### Option 5: Nginx (Self-hosted)

#### Setup:

1. **Build application:**
   ```bash
   npm run build
   ```

2. **Install Nginx:**
   ```bash
   sudo apt-get install nginx
   ```

3. **Create config file:**
   ```nginx
   # /etc/nginx/sites-available/legal-chatbot
   
   server {
     listen 80;
     server_name your-domain.com;
   
     root /var/www/legal-chatbot/dist;
   
     index index.html;
   
     location / {
       try_files $uri $uri/ /index.html;
     }
   
     location ~* ^/api/ {
       proxy_pass http://backend:8000;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection 'upgrade';
       proxy_set_header Host $host;
       proxy_cache_bypass $http_upgrade;
     }
   
     # Security headers
     add_header X-Frame-Options "SAMEORIGIN" always;
     add_header X-Content-Type-Options "nosniff" always;
     add_header X-XSS-Protection "1; mode=block" always;
     add_header Referrer-Policy "strict-origin-when-cross-origin" always;
     add_header Permissions-Policy "geolocation=(), microphone=(self)" always;
   }
   ```

4. **Enable SSL (Let's Encrypt):**
   ```bash
   sudo certbot --nginx -d your-domain.com
   ```

## Pre-deployment Checklist

- [ ] All environment variables configured
- [ ] Backend API URL updated for production
- [ ] Build completes without errors
- [ ] No console errors or warnings
- [ ] Responsive design tested on mobile
- [ ] All features tested:
  - Bot switching
  - Text input
  - Voice input
  - Citation display
  - Clear conversation
- [ ] Performance optimized:
  - Bundle size < 500KB (gzipped)
  - First Contentful Paint < 2s
- [ ] Security checks:
  - No sensitive data in code
  - HTTPS enabled in production
  - CORS properly configured
- [ ] SEO tags present
- [ ] Favicon configured
- [ ] Analytics configured (if needed)

## Performance Optimization

### Minification

Vite automatically minifies in production:

```bash
npm run build
```

### Gzip Compression

Enable on your server (nginx example):

```nginx
gzip on;
gzip_types text/plain text/css text/javascript application/json;
gzip_min_length 1000;
gzip_comp_level 6;
```

### Caching

Configure appropriate cache headers:

```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
  expires 1y;
  add_header Cache-Control "public, immutable";
}

location / {
  expires -1;
  add_header Cache-Control "public, max-age=0, must-revalidate";
}
```

### Image Optimization

- Use modern formats (WebP)
- Optimize images before deployment
- Use lazy loading where applicable

## Monitoring

### Application Performance Monitoring (APM)

Consider adding monitoring tools:

- **Sentry**: Error tracking
  ```typescript
  import * as Sentry from "@sentry/react";
  
  Sentry.init({
    dsn: "YOUR_DSN",
    environment: process.env.NODE_ENV,
  });
  ```

- **LogRocket**: Session recording
  ```typescript
  import LogRocket from 'logrocket';
  
  LogRocket.init('YOUR_APP_ID');
  ```

### Health Checks

Set up monitoring for:
- Backend API availability
- Response times
- Error rates
- User interactions

## Rollback Strategy

1. **Version control:**
   - Tag all releases
   - Maintain changelog

2. **Automated backups:**
   - Backup database regularly
   - Archive build artifacts

3. **Quick rollback:**
   - Use version tags for quick rollback
   - Keep previous builds available

## Environment-Specific Configuration

### Development

```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_ENABLE_VOICE=true
REACT_APP_ENABLE_TTS=false
```

### Staging

```env
REACT_APP_API_URL=https://staging-api.example.com
REACT_APP_ENABLE_VOICE=true
REACT_APP_ENABLE_TTS=true
```

### Production

```env
REACT_APP_API_URL=https://api.example.com
REACT_APP_ENABLE_VOICE=true
REACT_APP_ENABLE_TTS=true
```

## Continuous Deployment (CI/CD)

### GitHub Actions Example

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: cd frontend && npm ci
      
      - name: Build
        run: cd frontend && npm run build
        env:
          REACT_APP_API_URL: ${{ secrets.PROD_API_URL }}
      
      - name: Deploy to Vercel
        uses: vercel/action@master
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
```

## Post-Deployment

1. **Verify deployment:**
   - Check all pages load
   - Test all features
   - Verify API connectivity

2. **Monitor for errors:**
   - Check error logs
   - Monitor performance metrics
   - Test on various devices

3. **Gather feedback:**
   - Collect user feedback
   - Monitor error reports
   - Track performance metrics

---

**Last Updated**: September 2026
**Version**: 1.0.0
