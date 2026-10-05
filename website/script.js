/* ==========================================================================
   Ember IDE Website Script — Physics Engine, Flame AI Simulator & Interactivity
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    initEmberParticleCanvas();
    initPhysicsSandbox();
    initFlameAISimulator();
    initLightboxModal();
    initAntiGravityGlobalToggle();
    initCopyButtons();
    initMobileNav();
});

/* --------------------------------------------------------------------------
   1. Background Ember Particle Canvas
   -------------------------------------------------------------------------- */
function initEmberParticleCanvas() {
    const canvas = document.getElementById('bg-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    window.addEventListener('resize', () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    });

    const particles = [];
    const particleCount = 45;

    class Particle {
        constructor() {
            this.reset();
        }

        reset() {
            this.x = Math.random() * width;
            this.y = height + Math.random() * 100;
            this.radius = Math.random() * 2 + 0.8;
            this.vx = (Math.random() - 0.5) * 0.8;
            this.vy = -Math.random() * 1.5 - 0.5;
            this.alpha = Math.random() * 0.7 + 0.3;
            this.hue = Math.random() * 30 + 15; // Orange to gold embers
        }

        update() {
            this.x += this.vx;
            this.y += this.vy;
            this.alpha -= 0.003;

            if (this.alpha <= 0 || this.y < -10) {
                this.reset();
            }
        }

        draw() {
            ctx.save();
            ctx.globalAlpha = this.alpha;
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = `hsl(${this.hue}, 100%, 55%)`;
            ctx.shadowBlur = 10;
            ctx.shadowColor = `hsl(${this.hue}, 100%, 50%)`;
            ctx.fill();
            ctx.restore();
        }
    }

    for (let i = 0; i < particleCount; i++) {
        const p = new Particle();
        p.y = Math.random() * height; // Distribute initially
        particles.push(p);
    }

    function animate() {
        ctx.clearRect(0, 0, width, height);
        particles.forEach(p => {
            p.update();
            p.draw();
        });
        requestAnimationFrame(animate);
    }

    animate();
}

/* --------------------------------------------------------------------------
   2. Interactive Anti-Gravity Physics Sandbox Engine
   -------------------------------------------------------------------------- */
function initPhysicsSandbox() {
    const canvas = document.getElementById('physics-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const container = document.getElementById('physics-container');

    let width = canvas.width = container.clientWidth;
    let height = canvas.height = container.clientHeight;

    window.addEventListener('resize', () => {
        if (!container) return;
        width = canvas.width = container.clientWidth;
        height = canvas.height = container.clientHeight;
    });

    let gravityActive = false;
    let mouseX = -1000;
    let mouseY = -1000;
    let isDragging = false;
    let draggedNode = null;

    canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        mouseX = e.clientX - rect.left;
        mouseY = e.clientY - rect.top;

        if (isDragging && draggedNode) {
            draggedNode.x = mouseX;
            draggedNode.y = mouseY;
            draggedNode.vx = 0;
            draggedNode.vy = 0;
        }
    });

    canvas.addEventListener('mousedown', () => {
        // Find node under mouse
        for (let node of nodes) {
            const dx = mouseX - node.x;
            const dy = mouseY - node.y;
            if (Math.sqrt(dx * dx + dy * dy) < node.radius) {
                isDragging = true;
                draggedNode = node;
                break;
            }
        }
    });

    window.addEventListener('mouseup', () => {
        if (isDragging && draggedNode) {
            draggedNode.vx = (Math.random() - 0.5) * 6;
            draggedNode.vy = (Math.random() - 0.5) * 6;
        }
        isDragging = false;
        draggedNode = null;
    });

    const labels = [
        { text: 'Zig', icon: '⚡', color: '#f7a41d' },
        { text: 'Rust', icon: '🦀', color: '#ff5500' },
        { text: 'Python', icon: '🐍', color: '#3776ab' },
        { text: 'Flame AI', icon: '🔥', color: '#ff3300' },
        { text: 'C++', icon: '⚙️', color: '#00599c' },
        { text: 'Go', icon: '🐹', color: '#00add8' },
        { text: 'TypeScript', icon: '📘', color: '#3178c6' },
        { text: 'QScintilla', icon: '📝', color: '#20e070' },
        { text: 'LSP Client', icon: '🔌', color: '#a855f7' },
        { text: 'Terminal', icon: '💻', color: '#ffb700' }
    ];

    class Node {
        constructor(info, x, y) {
            this.text = info.text;
            this.icon = info.icon;
            this.color = info.color;
            this.x = x;
            this.y = y;
            this.radius = 38;
            this.vx = (Math.random() - 0.5) * 3;
            this.vy = (Math.random() - 0.5) * 3;
            this.mass = 1;
        }

        update() {
            if (isDragging && draggedNode === this) return;

            if (gravityActive) {
                this.vy += 0.25; // Apply downward gravity
            } else {
                // Anti-gravity floating drift
                this.vx += (Math.random() - 0.5) * 0.15;
                this.vy += (Math.random() - 0.5) * 0.15;
                // Cap speed in zero-G
                const speed = Math.sqrt(this.vx * this.vx + this.vy * this.vy);
                if (speed > 4) {
                    this.vx = (this.vx / speed) * 4;
                    this.vy = (this.vy / speed) * 4;
                }
            }

            // Mouse repulsion
            const dx = this.x - mouseX;
            const dy = this.y - mouseY;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 100 && dist > 0) {
                const force = (100 - dist) / 100;
                this.vx += (dx / dist) * force * 1.2;
                this.vy += (dy / dist) * force * 1.2;
            }

            this.x += this.vx;
            this.y += this.vy;

            // Boundary collision
            const bounce = gravityActive ? -0.7 : -0.9;
            if (this.x - this.radius < 0) {
                this.x = this.radius;
                this.vx *= bounce;
            }
            if (this.x + this.radius > width) {
                this.x = width - this.radius;
                this.vx *= bounce;
            }
            if (this.y - this.radius < 0) {
                this.y = this.radius;
                this.vy *= bounce;
            }
            if (this.y + this.radius > height) {
                this.y = height - this.radius;
                this.vy *= bounce;
            }
        }

        draw() {
            ctx.save();
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);

            // Glassmorphism node style
            ctx.fillStyle = 'rgba(22, 26, 38, 0.85)';
            ctx.shadowBlur = 15;
            ctx.shadowColor = this.color;
            ctx.fill();

            ctx.lineWidth = 2;
            ctx.strokeStyle = this.color;
            ctx.stroke();

            // Label text & icon
            ctx.shadowBlur = 0;
            ctx.fillStyle = '#ffffff';
            ctx.font = '600 13px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${this.icon} ${this.text}`, this.x, this.y);
            ctx.restore();
        }
    }

    const nodes = [];
    labels.forEach((info, idx) => {
        const x = 80 + (idx % 5) * ((width - 160) / 4);
        const y = 80 + Math.floor(idx / 5) * 120;
        nodes.push(new Node(info, x, y));
    });

    function resolveCollisions() {
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const n1 = nodes[i];
                const n2 = nodes[j];
                const dx = n2.x - n1.x;
                const dy = n2.y - n1.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const minDist = n1.radius + n2.radius;

                if (dist < minDist && dist > 0) {
                    const overlap = minDist - dist;
                    const nx = dx / dist;
                    const ny = dy / dist;

                    n1.x -= nx * overlap * 0.5;
                    n1.y -= ny * overlap * 0.5;
                    n2.x += nx * overlap * 0.5;
                    n2.y += ny * overlap * 0.5;

                    // Swap velocities along normal
                    const kx = n1.vx - n2.vx;
                    const ky = n1.vy - n2.vy;
                    const p = 2 * (nx * kx + ny * ky) / 2;

                    n1.vx -= p * nx;
                    n1.vy -= p * ny;
                    n2.vx += p * nx;
                    n2.vy += p * ny;
                }
            }
        }
    }

    function renderLoop() {
        ctx.clearRect(0, 0, width, height);
        resolveCollisions();
        nodes.forEach(n => {
            n.update();
            n.draw();
        });
        requestAnimationFrame(renderLoop);
    }

    renderLoop();

    // Sandbox Controls
    const toggleGravityBtn = document.getElementById('physics-toggle-gravity');
    const gravityText = document.getElementById('physics-gravity-text');
    const scatterBtn = document.getElementById('physics-scatter');
    const resetBtn = document.getElementById('physics-reset');

    if (toggleGravityBtn) {
        toggleGravityBtn.addEventListener('click', () => {
            gravityActive = !gravityActive;
            if (gravityText) {
                gravityText.textContent = gravityActive ? 'Earth Gravity (1G)' : 'Zero-G Active';
                gravityText.className = gravityActive ? 'text-green' : 'text-orange';
            }
        });
    }

    if (scatterBtn) {
        scatterBtn.addEventListener('click', () => {
            nodes.forEach(n => {
                n.vx = (Math.random() - 0.5) * 16;
                n.vy = (Math.random() - 0.5) * 16;
            });
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            gravityActive = false;
            if (gravityText) {
                gravityText.textContent = 'Zero-G Active';
                gravityText.className = 'text-orange';
            }
            nodes.forEach((n, idx) => {
                n.x = 80 + (idx % 5) * ((width - 160) / 4);
                n.y = 80 + Math.floor(idx / 5) * 120;
                n.vx = (Math.random() - 0.5) * 2;
                n.vy = (Math.random() - 0.5) * 2;
            });
        });
    }
}

/* --------------------------------------------------------------------------
   3. Interactive Flame AI Conversion Engine Simulator
   -------------------------------------------------------------------------- */
function initFlameAISimulator() {
    const targetSelect = document.getElementById('target-select');
    const flameInput = document.getElementById('flame-input');
    const flameOutput = document.getElementById('flame-output');
    const outputFilename = document.getElementById('output-filename');
    const convertBtn = document.getElementById('convert-btn');
    const resetBtn = document.getElementById('reset-flame-btn');
    const conversionStatus = document.getElementById('conversion-status');

    if (!targetSelect || !flameInput || !flameOutput) return;

    const sampleOutputs = {
        zig: {
            ext: 'output.zig',
            icon: 'fa-bolt',
            code: `// Generated by Flame AI Engine for Zig target\nconst std = @import("std");\n\npub fn calculate_fibonacci(n: u32) u32 {\n    if (n <= 1) return n;\n    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2);\n}\n\npub fn main() !void {\n    const stdout = std.io.getStdOut().writer();\n    const res = calculate_fibonacci(10);\n    try stdout.print("Fibonacci(10) = {d}\\n", .{res});\n}`
        },
        rust: {
            ext: 'output.rs',
            icon: 'fa-rust',
            code: `// Generated by Flame AI Engine for Rust target\n\npub fn calculate_fibonacci(n: u32) -> u32 {\n    match n {\n        0 | 1 => n,\n        _ => calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2),\n    }\n}\n\nfn main() {\n    let result = calculate_fibonacci(10);\n    println!("Fibonacci(10) = {}", result);\n}`
        },
        python: {
            ext: 'output.py',
            icon: 'fa-python',
            code: `# Generated by Flame AI Engine for Python target\n\ndef calculate_fibonacci(n: int) -> int:\n    if n <= 1:\n        return n\n    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)\n\nif __name__ == "__main__":\n    result = calculate_fibonacci(10)\n    print(f"Fibonacci(10) = {result}")`
        },
        cpp: {
            ext: 'output.cpp',
            icon: 'fa-code',
            code: `// Generated by Flame AI Engine for C++ target\n#include <iostream>\n\nuint32_t calculate_fibonacci(uint32_t n) {\n    if (n <= 1) return n;\n    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2);\n}\n\nint main() {\n    std::cout << "Fibonacci(10) = " << calculate_fibonacci(10) << std::endl;\n    return 0;\n}`
        },
        typescript: {
            ext: 'output.ts',
            icon: 'fa-js',
            code: `// Generated by Flame AI Engine for TypeScript target\n\nexport function calculateFibonacci(n: number): number {\n    if (n <= 1) return n;\n    return calculateFibonacci(n - 1) + calculateFibonacci(n - 2);\n}\n\nconsole.log(\`Fibonacci(10) = \${calculateFibonacci(10)}\`);`
        },
        go: {
            ext: 'output.go',
            icon: 'fa-golang',
            code: `// Generated by Flame AI Engine for Go target\npackage main\n\nimport "fmt"\n\nfunc calculateFibonacci(n uint32) uint32 {\n    if n <= 1 {\n        return n\n    }\n    return calculateFibonacci(n-1) + calculateFibonacci(n-2)\n}\n\nfunc main() {\n    fmt.Printf("Fibonacci(10) = %d\\n", calculateFibonacci(10))\n}`
        }
    };

    function runConversion() {
        const lang = targetSelect.value;
        const targetData = sampleOutputs[lang] || sampleOutputs.zig;

        if (conversionStatus) {
            conversionStatus.textContent = 'Converting...';
            conversionStatus.className = 'pane-badge';
        }

        flameOutput.textContent = '// Running Flame AI Dynamic Polyglot Resolution...';

        setTimeout(() => {
            if (outputFilename) {
                outputFilename.innerHTML = `<i class="fa-solid ${targetData.icon} icon-green"></i> ${targetData.ext}`;
            }
            flameOutput.textContent = targetData.code;

            if (conversionStatus) {
                conversionStatus.textContent = 'Conversion OK (0.038s)';
                conversionStatus.className = 'pane-badge badge-success';
            }
        }, 400);
    }

    if (convertBtn) {
        convertBtn.addEventListener('click', runConversion);
    }

    if (targetSelect) {
        targetSelect.addEventListener('change', runConversion);
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            targetSelect.value = 'zig';
            runConversion();
        });
    }

    // Initial render
    runConversion();
}

/* --------------------------------------------------------------------------
   4. Lightbox Modal for Screenshots
   -------------------------------------------------------------------------- */
function initLightboxModal() {
    const modal = document.getElementById('lightbox-modal');
    const modalImg = document.getElementById('lightbox-img');
    const caption = document.getElementById('lightbox-caption');
    const closeBtn = document.getElementById('lightbox-close');

    if (!modal || !modalImg) return;

    document.querySelectorAll('.lightbox-trigger, .lightbox-trigger-btn').forEach(elem => {
        elem.addEventListener('click', (e) => {
            e.stopPropagation();
            const imgSrc = elem.getAttribute('data-target') || elem.getAttribute('src');
            const altText = elem.getAttribute('alt') || 'Ember IDE Screenshot';

            modalImg.src = imgSrc;
            if (caption) caption.textContent = altText;
            modal.classList.add('active');
        });
    });

    if (closeBtn) {
        closeBtn.addEventListener('click', () => modal.classList.remove('active'));
    }

    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') modal.classList.remove('active');
    });
}

/* --------------------------------------------------------------------------
   5. Global Anti-Gravity / Zero-G Toggle
   -------------------------------------------------------------------------- */
function initAntiGravityGlobalToggle() {
    const toggleBtn = document.getElementById('antigravity-toggle');
    const heroBtn = document.getElementById('hero-antigravity-btn');
    const zeroGStatus = document.getElementById('zero-g-status');

    let isZeroGActive = false;

    function toggleZeroG() {
        isZeroGActive = !isZeroGActive;
        document.body.classList.toggle('floating-active', isZeroGActive);

        if (toggleBtn) {
            toggleBtn.classList.toggle('active', isZeroGActive);
        }

        if (zeroGStatus) {
            zeroGStatus.textContent = isZeroGActive ? 'Zero-G: ON' : 'Zero-G: OFF';
        }
    }

    if (toggleBtn) toggleBtn.addEventListener('click', toggleZeroG);
    if (heroBtn) heroBtn.addEventListener('click', toggleZeroG);
}

/* --------------------------------------------------------------------------
   6. Copy to Clipboard Utility
   -------------------------------------------------------------------------- */
function initCopyButtons() {
    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const textToCopy = btn.getAttribute('data-copy');
            if (!textToCopy) return;

            navigator.clipboard.writeText(textToCopy).then(() => {
                const icon = btn.querySelector('i');
                if (icon) {
                    icon.className = 'fa-solid fa-check icon-green';
                    setTimeout(() => {
                        icon.className = 'fa-regular fa-copy';
                    }, 2000);
                }
            });
        });
    });
}

/* --------------------------------------------------------------------------
   7. Mobile Navigation Menu Toggle
   -------------------------------------------------------------------------- */
function initMobileNav() {
    const toggle = document.getElementById('mobile-toggle');
    const navMenu = document.getElementById('nav-menu');

    if (!toggle || !navMenu) return;

    toggle.addEventListener('click', () => {
        const isOpen = navMenu.style.display === 'flex';
        navMenu.style.display = isOpen ? 'none' : 'flex';
        if (!isOpen) {
            navMenu.style.flexDirection = 'column';
            navMenu.style.position = 'absolute';
            navMenu.style.top = '70px';
            navMenu.style.left = '0';
            navMenu.style.width = '100%';
            navMenu.style.background = '#0d0f14';
            navMenu.style.padding = '20px';
        }
    });
}
