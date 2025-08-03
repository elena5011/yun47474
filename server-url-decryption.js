/**
 * Server-side URL Decryption Middleware
 * Node.js middleware for handling encrypted URLs
 */

const crypto = require('crypto');

class ServerURLDecryption {
    constructor(secretKey = 'your-secret-key-32-chars-long!!') {
        this.secretKey = secretKey;
        this.algorithm = 'aes-256-gcm';
    }

    /**
     * Decrypt an encrypted URL using Node.js crypto
     * @param {string} encryptedURL - Base64 encoded encrypted URL
     * @returns {string} - Decrypted URL path and query
     */
    decryptURL(encryptedURL) {
        try {
            // Restore base64 padding and convert from URL-safe
            const base64 = encryptedURL
                .replace(/-/g, '+')
                .replace(/_/g, '/')
                .padEnd(encryptedURL.length + (4 - encryptedURL.length % 4) % 4, '=');
            
            const combined = Buffer.from(base64, 'base64');
            
            // Extract IV and encrypted data
            const iv = combined.slice(0, 12);
            const encryptedData = combined.slice(12, -16); // Exclude auth tag
            const authTag = combined.slice(-16);
            
            // Create decipher
            const decipher = crypto.createDecipherGCM(this.algorithm, Buffer.from(this.secretKey));
            decipher.setIV(iv);
            decipher.setAuthTag(authTag);
            
            let decrypted = decipher.update(encryptedData, null, 'utf8');
            decrypted += decipher.final('utf8');
            
            return decrypted;
        } catch (error) {
            console.error('Server decryption error:', error);
            throw new Error('Failed to decrypt URL');
        }
    }

    /**
     * Encrypt a URL using Node.js crypto (for server-side generation)
     * @param {string} urlPath - The URL path and query to encrypt
     * @returns {string} - Base64 encoded encrypted URL
     */
    encryptURL(urlPath) {
        try {
            const iv = crypto.randomBytes(12);
            const cipher = crypto.createCipherGCM(this.algorithm, Buffer.from(this.secretKey));
            cipher.setIV(iv);
            
            let encrypted = cipher.update(urlPath, 'utf8');
            encrypted = Buffer.concat([encrypted, cipher.final()]);
            
            const authTag = cipher.getAuthTag();
            
            // Combine IV, encrypted data, and auth tag
            const combined = Buffer.concat([iv, encrypted, authTag]);
            
            // Convert to base64 and make URL-safe
            return combined.toString('base64')
                .replace(/\+/g, '-')
                .replace(/\//g, '_')
                .replace(/=/g, '');
        } catch (error) {
            console.error('Server encryption error:', error);
            throw new Error('Failed to encrypt URL');
        }
    }

    /**
     * Express.js middleware for handling encrypted URLs
     */
    middleware() {
        return (req, res, next) => {
            // Check if the URL starts with /secure/
            if (req.path.startsWith('/secure/')) {
                const encryptedPart = req.path.replace('/secure/', '');
                
                try {
                    const decryptedURL = this.decryptURL(encryptedPart);
                    
                    // Parse the decrypted URL
                    const url = new URL(decryptedURL, `http://${req.get('host')}`);
                    
                    // Update request object with decrypted path and query
                    req.originalUrl = req.url;
                    req.url = decryptedURL;
                    req.path = url.pathname;
                    req.query = Object.fromEntries(url.searchParams);
                    
                    // Add a flag to indicate this was an encrypted URL
                    req.wasEncrypted = true;
                    req.encryptedPath = encryptedPart;
                    
                    console.log(`Decrypted URL: ${decryptedURL}`);
                } catch (error) {
                    console.error('Failed to decrypt URL:', error);
                    return res.status(400).json({ error: 'Invalid encrypted URL' });
                }
            }
            
            next();
        };
    }

    /**
     * Next.js middleware for handling encrypted URLs
     */
    nextMiddleware() {
        return (request) => {
            const { pathname } = request.nextUrl;
            
            if (pathname.startsWith('/secure/')) {
                const encryptedPart = pathname.replace('/secure/', '');
                
                try {
                    const decryptedURL = this.decryptURL(encryptedPart);
                    const url = new URL(decryptedURL, request.nextUrl.origin);
                    
                    // Rewrite to the decrypted URL
                    return Response.redirect(url.toString());
                } catch (error) {
                    console.error('Failed to decrypt URL:', error);
                    return new Response('Invalid encrypted URL', { status: 400 });
                }
            }
        };
    }
}

/**
 * Express.js example usage
 */
function createExpressExample() {
    const express = require('express');
    const path = require('path');
    const app = express();
    
    const urlDecryption = new ServerURLDecryption();
    
    // Serve static files
    app.use(express.static('public'));
    
    // Apply URL decryption middleware
    app.use(urlDecryption.middleware());
    
    // Example routes
    app.get('/', (req, res) => {
        res.sendFile(path.join(__dirname, 'public', 'index.html'));
    });
    
    app.get('/users/:id', (req, res) => {
        const wasEncrypted = req.wasEncrypted ? ' (decrypted)' : '';
        res.json({
            message: `User ${req.params.id}${wasEncrypted}`,
            query: req.query,
            wasEncrypted: req.wasEncrypted
        });
    });
    
    app.get('/search', (req, res) => {
        const wasEncrypted = req.wasEncrypted ? ' (decrypted)' : '';
        res.json({
            message: `Search results${wasEncrypted}`,
            query: req.query,
            wasEncrypted: req.wasEncrypted
        });
    });
    
    // API endpoint to encrypt URLs
    app.post('/api/encrypt-url', express.json(), (req, res) => {
        try {
            const { url } = req.body;
            const encrypted = urlDecryption.encryptURL(url);
            res.json({ encryptedURL: `/secure/${encrypted}` });
        } catch (error) {
            res.status(400).json({ error: 'Failed to encrypt URL' });
        }
    });
    
    const PORT = process.env.PORT || 3000;
    app.listen(PORT, () => {
        console.log(`Server running on port ${PORT}`);
        console.log(`Visit http://localhost:${PORT}`);
    });
    
    return app;
}

/**
 * Generic middleware factory for different frameworks
 */
function createMiddleware(framework = 'express') {
    const urlDecryption = new ServerURLDecryption();
    
    switch (framework) {
        case 'express':
            return urlDecryption.middleware();
        case 'nextjs':
            return urlDecryption.nextMiddleware();
        default:
            throw new Error(`Unsupported framework: ${framework}`);
    }
}

module.exports = {
    ServerURLDecryption,
    createExpressExample,
    createMiddleware
};

// If this file is run directly, start the Express example
if (require.main === module) {
    createExpressExample();
}