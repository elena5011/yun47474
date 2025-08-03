/**
 * URL Encryption Utility
 * Encrypts full URL paths and query parameters for secure transmission
 */

class URLEncryption {
    constructor(secretKey = 'your-secret-key-32-chars-long!!') {
        this.secretKey = secretKey;
        this.algorithm = 'AES-GCM';
        this.keyLength = 256;
    }

    /**
     * Generate a cryptographic key from the secret key
     */
    async generateKey() {
        const encoder = new TextEncoder();
        const keyData = encoder.encode(this.secretKey);
        
        return await crypto.subtle.importKey(
            'raw',
            keyData,
            { name: this.algorithm },
            false,
            ['encrypt', 'decrypt']
        );
    }

    /**
     * Encrypt a URL path and query string
     * @param {string} urlPath - The URL path and query to encrypt (e.g., "/users/123?name=john&age=30")
     * @returns {Promise<string>} - Base64 encoded encrypted URL
     */
    async encryptURL(urlPath) {
        try {
            const key = await this.generateKey();
            const encoder = new TextEncoder();
            const data = encoder.encode(urlPath);
            
            // Generate a random IV
            const iv = crypto.getRandomValues(new Uint8Array(12));
            
            const encryptedData = await crypto.subtle.encrypt(
                {
                    name: this.algorithm,
                    iv: iv
                },
                key,
                data
            );
            
            // Combine IV and encrypted data
            const combined = new Uint8Array(iv.length + encryptedData.byteLength);
            combined.set(iv);
            combined.set(new Uint8Array(encryptedData), iv.length);
            
            // Convert to base64 and make URL-safe
            return btoa(String.fromCharCode(...combined))
                .replace(/\+/g, '-')
                .replace(/\//g, '_')
                .replace(/=/g, '');
        } catch (error) {
            console.error('Encryption error:', error);
            throw new Error('Failed to encrypt URL');
        }
    }

    /**
     * Decrypt an encrypted URL
     * @param {string} encryptedURL - Base64 encoded encrypted URL
     * @returns {Promise<string>} - Decrypted URL path and query
     */
    async decryptURL(encryptedURL) {
        try {
            // Restore base64 padding and convert from URL-safe
            const base64 = encryptedURL
                .replace(/-/g, '+')
                .replace(/_/g, '/')
                .padEnd(encryptedURL.length + (4 - encryptedURL.length % 4) % 4, '=');
            
            const combined = new Uint8Array(
                atob(base64).split('').map(char => char.charCodeAt(0))
            );
            
            // Extract IV and encrypted data
            const iv = combined.slice(0, 12);
            const encryptedData = combined.slice(12);
            
            const key = await this.generateKey();
            
            const decryptedData = await crypto.subtle.decrypt(
                {
                    name: this.algorithm,
                    iv: iv
                },
                key,
                encryptedData
            );
            
            const decoder = new TextDecoder();
            return decoder.decode(decryptedData);
        } catch (error) {
            console.error('Decryption error:', error);
            throw new Error('Failed to decrypt URL');
        }
    }

    /**
     * Encrypt current page URL and update the browser URL
     */
    async encryptCurrentURL() {
        const currentPath = window.location.pathname + window.location.search;
        const encryptedPath = await this.encryptURL(currentPath);
        
        // Update URL without page reload
        const newURL = `${window.location.origin}/secure/${encryptedPath}`;
        window.history.pushState({}, '', newURL);
        
        return newURL;
    }

    /**
     * Create encrypted links for navigation
     * @param {string} targetURL - The URL to encrypt and navigate to
     * @returns {Promise<string>} - Encrypted URL for navigation
     */
    async createEncryptedLink(targetURL) {
        const encryptedPath = await this.encryptURL(targetURL);
        return `${window.location.origin}/secure/${encryptedPath}`;
    }
}

// Utility functions for easy integration
const urlEncryption = new URLEncryption();

/**
 * Encrypt a URL and return the encrypted version
 */
async function encryptURL(url) {
    return await urlEncryption.encryptURL(url);
}

/**
 * Decrypt an encrypted URL
 */
async function decryptURL(encryptedURL) {
    return await urlEncryption.decryptURL(encryptedURL);
}

/**
 * Replace all links on the page with encrypted versions
 */
async function encryptAllLinks() {
    const links = document.querySelectorAll('a[href]');
    
    for (const link of links) {
        const href = link.getAttribute('href');
        
        // Skip external links and already encrypted links
        if (href.startsWith('http') && !href.includes(window.location.hostname)) {
            continue;
        }
        if (href.startsWith('/secure/')) {
            continue;
        }
        
        try {
            const encryptedURL = await urlEncryption.createEncryptedLink(href);
            link.setAttribute('href', encryptedURL);
            link.setAttribute('data-original-href', href);
        } catch (error) {
            console.warn('Failed to encrypt link:', href, error);
        }
    }
}

/**
 * Handle encrypted URLs on page load
 */
async function handleEncryptedURL() {
    const path = window.location.pathname;
    
    if (path.startsWith('/secure/')) {
        const encryptedPart = path.replace('/secure/', '');
        
        try {
            const decryptedURL = await urlEncryption.decryptURL(encryptedPart);
            console.log('Decrypted URL:', decryptedURL);
            
            // You can now use the decrypted URL to load the appropriate content
            // This would typically be handled by your router or server
            return decryptedURL;
        } catch (error) {
            console.error('Failed to decrypt URL:', error);
            // Redirect to error page or home
            window.location.href = '/';
        }
    }
}

// Auto-initialize when DOM is loaded
if (typeof window !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        handleEncryptedURL();
    });
}

// Export for use in Node.js environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { URLEncryption, encryptURL, decryptURL };
}