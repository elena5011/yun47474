/**
 * Test script for URL encryption/decryption functionality
 */

const { ServerURLDecryption } = require('./server-url-decryption');

// Test data
const testURLs = [
    '/users/123?name=john&age=30',
    '/search?q=javascript&category=tutorials&sort=date',
    '/dashboard?tab=analytics&period=monthly&user=admin',
    '/settings?section=privacy&advanced=true&theme=dark',
    '/api/v1/data?limit=100&offset=50&fields=id,name,email'
];

async function runTests() {
    console.log('🧪 Starting URL Encryption Tests...\n');
    
    const urlDecryption = new ServerURLDecryption();
    let passedTests = 0;
    let totalTests = 0;

    for (const originalURL of testURLs) {
        totalTests++;
        console.log(`Test ${totalTests}: ${originalURL}`);
        
        try {
            // Encrypt the URL
            const encrypted = urlDecryption.encryptURL(originalURL);
            console.log(`  ✓ Encrypted: ${encrypted.substring(0, 50)}...`);
            
            // Decrypt the URL
            const decrypted = urlDecryption.decryptURL(encrypted);
            console.log(`  ✓ Decrypted: ${decrypted}`);
            
            // Verify they match
            if (originalURL === decrypted) {
                console.log('  ✅ PASS: Original and decrypted URLs match\n');
                passedTests++;
            } else {
                console.log('  ❌ FAIL: URLs do not match');
                console.log(`     Expected: ${originalURL}`);
                console.log(`     Got:      ${decrypted}\n`);
            }
        } catch (error) {
            console.log(`  ❌ FAIL: ${error.message}\n`);
        }
    }

    // Test invalid decryption
    totalTests++;
    console.log(`Test ${totalTests}: Invalid encrypted data`);
    try {
        urlDecryption.decryptURL('invalid-data');
        console.log('  ❌ FAIL: Should have thrown an error\n');
    } catch (error) {
        console.log('  ✅ PASS: Correctly rejected invalid data\n');
        passedTests++;
    }

    // Test empty URL
    totalTests++;
    console.log(`Test ${totalTests}: Empty URL`);
    try {
        const encrypted = urlDecryption.encryptURL('');
        const decrypted = urlDecryption.decryptURL(encrypted);
        if (decrypted === '') {
            console.log('  ✅ PASS: Empty URL handled correctly\n');
            passedTests++;
        } else {
            console.log('  ❌ FAIL: Empty URL not handled correctly\n');
        }
    } catch (error) {
        console.log(`  ❌ FAIL: ${error.message}\n`);
    }

    // Test URL-safe encoding
    totalTests++;
    console.log(`Test ${totalTests}: URL-safe encoding`);
    try {
        const testURL = '/test?data=+/=&special=true';
        const encrypted = urlDecryption.encryptURL(testURL);
        
        // Check that encrypted string is URL-safe (no +, /, or = characters)
        const hasUnsafeChars = /[+/=]/.test(encrypted);
        if (!hasUnsafeChars) {
            console.log('  ✅ PASS: Encrypted URL is URL-safe\n');
            passedTests++;
        } else {
            console.log('  ❌ FAIL: Encrypted URL contains unsafe characters\n');
        }
    } catch (error) {
        console.log(`  ❌ FAIL: ${error.message}\n`);
    }

    // Summary
    console.log('📊 Test Results:');
    console.log(`   Passed: ${passedTests}/${totalTests}`);
    console.log(`   Success Rate: ${((passedTests / totalTests) * 100).toFixed(1)}%`);
    
    if (passedTests === totalTests) {
        console.log('   🎉 All tests passed!');
        return true;
    } else {
        console.log('   ⚠️  Some tests failed.');
        return false;
    }
}

// Performance test
async function performanceTest() {
    console.log('\n⚡ Performance Test...');
    
    const urlDecryption = new ServerURLDecryption();
    const testURL = '/users/123?name=john&age=30&role=admin';
    const iterations = 1000;
    
    // Encryption performance
    const encryptStart = Date.now();
    const encryptedURLs = [];
    
    for (let i = 0; i < iterations; i++) {
        encryptedURLs.push(urlDecryption.encryptURL(testURL));
    }
    
    const encryptTime = Date.now() - encryptStart;
    
    // Decryption performance
    const decryptStart = Date.now();
    
    for (let i = 0; i < iterations; i++) {
        urlDecryption.decryptURL(encryptedURLs[i]);
    }
    
    const decryptTime = Date.now() - decryptStart;
    
    console.log(`   Encryption: ${iterations} operations in ${encryptTime}ms (${(encryptTime/iterations).toFixed(2)}ms per operation)`);
    console.log(`   Decryption: ${iterations} operations in ${decryptTime}ms (${(decryptTime/iterations).toFixed(2)}ms per operation)`);
    console.log(`   Total: ${encryptTime + decryptTime}ms for ${iterations * 2} operations`);
}

// Run all tests
async function main() {
    const success = await runTests();
    await performanceTest();
    
    process.exit(success ? 0 : 1);
}

// Run tests if this file is executed directly
if (require.main === module) {
    main().catch(console.error);
}

module.exports = { runTests, performanceTest };