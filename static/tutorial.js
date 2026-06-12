/**
 * Studio Tutorial Engine
 * "动态阴影拼图" — 画布上出现半透明阴影节点引导放置
 * 放置时自动吸附 + 连线 + TransformUp 音效
 * 一组完成播放成就 chime / 30秒无操作弹出 Auto 按钮
 */

// ============================================================
//  音效
// ============================================================

let _transformUpBuffer = null;
let _audioCtx = null;

function _getAudioCtx() {
    try {
        if (!_audioCtx) _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        return _audioCtx;
    } catch(e) { return null; }
}

async function loadTransformUpSound() {
    try {
        const ctx = _getAudioCtx();
        if (!ctx) return;
        var resp = await fetch('/static/sounds/transformup.mp3');
        if (!resp.ok) { resp = await fetch('/static/sounds/transformup.wav'); }
        if (!resp.ok) { console.warn('TransformUp sound not found at /static/sounds/transformup.mp3'); return; }
        const buf = await resp.arrayBuffer();
        _transformUpBuffer = await ctx.decodeAudioData(buf);
    } catch(e) { console.warn('TransformUp sound not loaded', e); }
}

function playTransformUp() {
    if (!_transformUpBuffer) return;
    try {
        const ctx = _getAudioCtx();
        if (!ctx) return;
        const src = ctx.createBufferSource();
        src.buffer = _transformUpBuffer;
        const gain = ctx.createGain();
        gain.gain.value = 0.25;
        src.connect(gain).connect(ctx.destination);
        src.start(0);
    } catch(e) {}
}

function playAchievementChime() {
    try {
        const ctx = _getAudioCtx();
        if (!ctx) return;
        [523.25, 659.25, 783.99].forEach(function(freq, i) {
            var osc = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.value = freq;
            gain.gain.setValueAtTime(0.15, ctx.currentTime + i * 0.12);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.12 + 0.5);
            osc.connect(gain).connect(ctx.destination);
            osc.start(ctx.currentTime + i * 0.12);
            osc.stop(ctx.currentTime + i * 0.12 + 0.5);
        });
    } catch(e) {}
}


// ============================================================
//  教程数据
// ============================================================

var TUTORIAL_MODULES = {
    lenet5: {
        title: 'Build LeNet-5',
        description: 'Classic CNN for handwritten digit recognition',
        steps: [
            { id:1,  expects:{action:'add_node',type:'MNIST'},         pos:[80,200],    bubble:'MNIST handwritten digits.\n28x28 grayscale, 10 classes (0-9).' },
            { id:2,  expects:{action:'add_node',type:'Conv2D'},        pos:[340,180],   bubble:'Conv2D: 6 filters of 5x5.\nExtracts edges and basic shapes from the input.',          autoWire:[{fromStep:1,fromPort:0,toPort:0}] },
            { id:3,  expects:{action:'add_node',type:'MaxPool'},       pos:[600,180],   bubble:'MaxPool 2x2: downsamples.\nReduces 24x24 to 12x12, keeps strongest activations.',        autoWire:[{fromStep:2,fromPort:0,toPort:0}] },
            { id:4,  expects:{action:'add_node',type:'Conv2D'},        pos:[340,280],   bubble:'Conv2D: 16 filters of 5x5.\nDeeper layer learns combinations of simple features.',      autoWire:[{fromStep:3,fromPort:0,toPort:0}], hasAuto:true },
            { id:5,  expects:{action:'add_node',type:'MaxPool'},       pos:[600,280],   bubble:'Second pooling: 8x8 to 4x4.',                                                              autoWire:[{fromStep:4,fromPort:0,toPort:0}] },
            { id:6,  expects:{action:'add_node',type:'Flatten'},       pos:[860,230],   bubble:'Flatten: reshape 4x4x16=256 into a flat vector.\nBridges convolution layers to dense layers.', autoWire:[{fromStep:5,fromPort:0,toPort:0}] },
            { id:7,  expects:{action:'add_node',type:'Dense'},         pos:[80,380],    bubble:'Dense(120): fully-connected layer.\nCombines all extracted features before classification.', autoWire:[{fromStep:6,fromPort:0,toPort:0}] },
            { id:8,  expects:{action:'add_node',type:'Dense'},         pos:[340,380],   bubble:'Dense(84): intermediate dense layer.',                                                      autoWire:[{fromStep:7,fromPort:0,toPort:0}], hasAuto:true },
            { id:9,  expects:{action:'add_node',type:'Dense'},         pos:[600,380],   bubble:'Dense(10): output layer.\nOne neuron per digit class (0-9).',                               autoWire:[{fromStep:8,fromPort:0,toPort:0}] },
            { id:10, expects:{action:'add_node',type:'Loss'},          pos:[860,380],   bubble:'Loss node: CrossEntropy.\nComputes error between prediction and true label.\nOptimizer: Adam, learning rate: 0.001.', autoWire:[{fromStep:9,fromPort:0,toPort:0}], isFinal:true },
        ]
    },
    cnn: {
        title: 'Build a CNN',
        description: 'Modern conv net with BatchNorm for CIFAR-10',
        steps: [
            { id:1,  expects:{action:'add_node',type:'CIFAR-10'},      pos:[80,200],    bubble:'CIFAR-10: 32x32 RGB images, 10 classes.\nMore complex than MNIST.' },
            { id:2,  expects:{action:'add_node',type:'Conv2D'},        pos:[340,180],   bubble:'Conv2D: 32 filters, 3x3, padding=1.\nPreserves spatial resolution for deeper stacking.',   autoWire:[{fromStep:1,fromPort:0,toPort:0}] },
            { id:3,  expects:{action:'add_node',type:'BatchNorm2d'},   pos:[600,180],   bubble:'BatchNorm2d: normalizes activations.\nStabilizes training, reduces internal covariate shift.', autoWire:[{fromStep:2,fromPort:0,toPort:0}] },
            { id:4,  expects:{action:'add_node',type:'ReLU'},          pos:[860,180],   bubble:'ReLU: max(0, x).\nIntroduces non-linearity required for deep networks.',                     autoWire:[{fromStep:3,fromPort:0,toPort:0}] },
            { id:5,  expects:{action:'add_node',type:'MaxPool'},       pos:[600,300],   bubble:'MaxPool 2x2: spatial downsampling.',                                                         autoWire:[{fromStep:4,fromPort:0,toPort:0}] },
            { id:6,  expects:{action:'add_node',type:'Flatten'},       pos:[600,400],   bubble:'Flatten for classifier head.',                                                                 autoWire:[{fromStep:5,fromPort:0,toPort:0}], hasAuto:true },
            { id:7,  expects:{action:'add_node',type:'Dense'},         pos:[600,500],   bubble:'Dense(10): CIFAR-10 output layer.',                                                           autoWire:[{fromStep:6,fromPort:0,toPort:0}] },
            { id:8,  expects:{action:'add_node',type:'Loss'},          pos:[600,580],   bubble:'CrossEntropy loss for 10-class classification.',                                               autoWire:[{fromStep:7,fromPort:0,toPort:0}], isFinal:true },
        ]
    },
    resnet: {
        title: 'Build ResNet-18 Lite',
        description: 'Residual connection with skip pathway',
        steps: [
            { id:1,  expects:{action:'add_node',type:'MNIST'},         pos:[80,180],    bubble:'MNIST input.' },
            { id:2,  expects:{action:'add_node',type:'Conv2D'},        pos:[340,140],   bubble:'Conv2D: 16 filters, 3x3, pad=1.\nStart of residual block.',                                   autoWire:[{fromStep:1,fromPort:0,toPort:0}] },
            { id:3,  expects:{action:'add_node',type:'BatchNorm2d'},   pos:[600,140],   bubble:'BatchNorm: stabilize residual path.',                                                          autoWire:[{fromStep:2,fromPort:0,toPort:0}] },
            { id:4,  expects:{action:'add_node',type:'ReLU'},          pos:[860,140],   bubble:'ReLU activation.\nOutput branches to BOTH step 5 AND step 7 (skip).',                         autoWire:[{fromStep:3,fromPort:0,toPort:0}] },
            { id:5,  expects:{action:'add_node',type:'Conv2D'},        pos:[340,280],   bubble:'Conv2D: second conv in residual block.',                                                       autoWire:[{fromStep:4,fromPort:0,toPort:0}] },
            { id:6,  expects:{action:'add_node',type:'BatchNorm2d'},   pos:[600,280],   bubble:'BatchNorm after second conv.',                                                                 autoWire:[{fromStep:5,fromPort:0,toPort:0}] },
            { id:7,  expects:{action:'add_node',type:'Add'},           pos:[1120,200],  bubble:'Add: residual skip-connection.\nMain path connects here (Step 6).\nShortcut path from Step 4 (ReLU).\nThis identity shortcut lets gradient flow through.', autoWire:[{fromStep:4,fromPort:0,toPort:0},{fromStep:6,fromPort:0,toPort:1}], highlightArrows:true },
            { id:8,  expects:{action:'add_node',type:'ReLU'},          pos:[1350,200],  bubble:'ReLU after residual add.',                                                                    autoWire:[{fromStep:7,fromPort:0,toPort:0}] },
            { id:9,  expects:{action:'add_node',type:'MaxPool'},       pos:[1350,320],  bubble:'MaxPool: downsampling.',                                                                      autoWire:[{fromStep:8,fromPort:0,toPort:0}] },
            { id:10, expects:{action:'add_node',type:'Flatten'},       pos:[1120,400],  bubble:'Flatten → classifier.',                                                                       autoWire:[{fromStep:9,fromPort:0,toPort:0}], hasAuto:true },
            { id:11, expects:{action:'add_node',type:'Dense'},         pos:[1120,480],  bubble:'Dense(10): digit classification.',                                                            autoWire:[{fromStep:10,fromPort:0,toPort:0}] },
            { id:12, expects:{action:'add_node',type:'Loss'},          pos:[1120,560],  bubble:'CrossEntropy loss.',                                                                          autoWire:[{fromStep:11,fromPort:0,toPort:0}], isFinal:true },
        ]
    }
};


// ============================================================
//  Tutorial Engine
// ============================================================

function StudioTutorial(graph, canvasEl) {
    this.graph = graph;
    this.canvas = canvasEl;
    this.active = false;
    this.module = null;
    this.stepIndex = 0;
    this.shadowNodes = [];
    this.placedNodes = [];
    this.bubbleEl = null;
    this.autoBtnEl = null;
    this.idleTimer = null;
    this._origOnNodeAdded = null;
    this._origOnConnectionChange = null;
    this._origOnDrawForeground = null;
    this._animFrame = null;
}

StudioTutorial.prototype.start = function(moduleKey) {
    if (this.active) this.stop(true);
    this.active = true;
    this.module = TUTORIAL_MODULES[moduleKey];
    this.stepIndex = 0;
    this.shadowNodes = [];
    this.placedNodes = [];
    this._installHooks();
    this._showStep(0);
    loadTransformUpSound().catch(function(){});
    this._startPulse();
};

StudioTutorial.prototype.stop = function(silent) {
    this.active = false;
    this._hideBubble();
    this._hideAutoBtn();
    clearTimeout(this.idleTimer);
    this._uninstallHooks();
    this._clearShadows();
    this._stopPulse();
    if (!silent) {
        alert('[Tutorial] ' + this.module.title + ' module exited.\nPlaced nodes remain on your canvas.');
    }
};

StudioTutorial.prototype._showStep = function(index) {
    var self = this;
    this.stepIndex = index;
    var step = this.module.steps[index];
    if (!step) {
        this._finishModule();
        return;
    }
    this._clearShadows();
    this._createShadow(step);
    this._showBubble(step);
    clearTimeout(this.idleTimer);
    if (step.hasAuto) {
        var that = this;
        this.idleTimer = setTimeout(function(){ that._showAutoBtn(step); }, 30000);
    }
};

StudioTutorial.prototype._createShadow = function(step) {
    var node = LiteGraph.createNode(step.expects.type);
    node.pos = step.pos;
    node.bgcolor = 'rgba(83, 74, 183, 0.08)';
    node.boxcolor = 'rgba(83, 74, 183, 0.45)';
    node.flags = node.flags || {};
    node.flags.pinned = true;
    node.mode = 3;
    node.isTutorialShadow = true;
    node._stepId = step.id;
    if (step.expects.type === 'Loss') {
        node.properties = node.properties || {};
        node.properties.kind = 'CrossEntropy';
        node.properties.optimizer = 'Adam';
        node.properties.lr = 0.001;
        node.properties.epochs = 5;
        node.properties.target = 'Label';
    }
    this.graph.add(node);
    this.shadowNodes.push(node);

    // Auto-wire to previous node if specified
    if (step.autoWire && step.autoWire.length > 0 && this.placedNodes.length > 0) {
        var self = this;
        step.autoWire.forEach(function(w) {
            var pid = self.module.steps[w.fromStep - 1];
            if (!pid) return;
            var pNodes = self.placedNodes.filter(function(n){ return n._stepId === pid.id; });
            if (pNodes.length) {
                setTimeout(function(){
                    pNodes[0].connect(w.fromPort || 0, node, w.toPort || 0);
                }, 50);
            }
        });
    }
};

StudioTutorial.prototype._clearShadows = function() {
    var self = this;
    this.shadowNodes.forEach(function(n){
        try { self.graph.remove(n); } catch(e) {}
    });
    this.shadowNodes = [];
};

StudioTutorial.prototype._showBubble = function(step) {
    this._hideBubble();
    if (!step.bubble) return;
    var el = document.createElement('div');
    el.className = 'tutorial-bubble';
    el.innerText = step.bubble;
    var shadow = this.shadowNodes[0];
    if (shadow) {
        var canvasRect = this.canvas.canvas.getBoundingClientRect();
        el.style.position = 'fixed';
        el.style.left = (canvasRect.left + 20) + 'px';
        el.style.top = (canvasRect.top + canvasRect.height - 120) + 'px';
    }
    document.body.appendChild(el);
    this.bubbleEl = el;
};

StudioTutorial.prototype._hideBubble = function() {
    if (this.bubbleEl) { this.bubbleEl.remove(); this.bubbleEl = null; }
};

StudioTutorial.prototype._showAutoBtn = function(step) {
    this._hideAutoBtn();
    var self = this;
    var el = document.createElement('button');
    el.className = 'tutorial-auto-btn';
    el.textContent = 'Auto-fill remaining steps';
    el.onclick = function(){ self._autoComplete(); };
    var canvasRect = this.canvas.canvas.getBoundingClientRect();
    el.style.position = 'fixed';
    el.style.left = (canvasRect.left + 20) + 'px';
    el.style.top = (canvasRect.top + canvasRect.height - 80) + 'px';
    document.body.appendChild(el);
    this.autoBtnEl = el;
};

StudioTutorial.prototype._hideAutoBtn = function() {
    if (this.autoBtnEl) { this.autoBtnEl.remove(); this.autoBtnEl = null; }
};

StudioTutorial.prototype._autoComplete = function() {
    this._hideAutoBtn();
    var self = this;
    var remaining = this.module.steps.slice(this.stepIndex);
    remaining.forEach(function(step, i) {
        setTimeout(function(){
            var node = LiteGraph.createNode(step.expects.type);
            node.pos = step.pos;
            node._stepId = step.id;
            node.bgcolor = 'rgba(83, 74, 183, 0.12)';
            node.boxcolor = '#534AB7';
            self.graph.add(node);
            self.placedNodes.push(node);
            playTransformUp();
            if (step.autoWire && step.autoWire.length) {
                step.autoWire.forEach(function(w){
                    var pid = self.module.steps[w.fromStep - 1];
                    if (!pid) return;
                    var pNodes = self.placedNodes.filter(function(n){ return n._stepId === pid.id; });
                    if (pNodes.length) {
                        pNodes[0].connect(w.fromPort || 0, node, w.toPort || 0);
                    }
                });
            }
            if (i === remaining.length - 1) {
                setTimeout(function(){
                    self._clearShadows();
                    playAchievementChime();
                    self._completeAll();
                }, 400);
            }
        }, i * 250);
    });
};

StudioTutorial.prototype._finishModule = function() {
    this._clearShadows();
    this._hideBubble();
    this._hideAutoBtn();
    this._uninstallHooks();
    this._stopPulse();
    playAchievementChime();
    this.active = false;
    var title = this.module.title;
    this.module = null;
    setTimeout(function(){
        alert('[Tutorial] ' + title + ' complete!\n\nModel stays on your canvas.\nYou can now train it in the Arena or keep editing.');
    }, 300);
};

StudioTutorial.prototype._completeAll = function() {
    this._hideBubble();
    this._hideAutoBtn();
    this._uninstallHooks();
    this._stopPulse();
    var title = this.module ? this.module.title : 'Module';
    this.active = false;
    this.module = null;
    setTimeout(function(){
        alert('[Tutorial] ' + title + ' complete!\n\nAll nodes placed. Canvas is yours.');
    }, 300);
};

StudioTutorial.prototype._installHooks = function() {
    var self = this;
    this._origOnNodeAdded = this.graph.onNodeAdded;
    this._origOnConnectionChange = this.graph.onConnectionChange;

    this.graph.onNodeAdded = function(node) {
        if (self._origOnNodeAdded) self._origOnNodeAdded.call(this, node);
        if (!self.active || node.isTutorialShadow) return;
        var step = self.module && self.module.steps ? self.module.steps[self.stepIndex] : null;
        if (!step) return;
        if (node.type === step.expects.type) {
            var shadow = self.shadowNodes[0];
            if (shadow) {
                var dx = node.pos[0] - shadow.pos[0];
                var dy = node.pos[1] - shadow.pos[1];
                if (Math.sqrt(dx*dx + dy*dy) < 250) {
                    node.pos = [shadow.pos[0], shadow.pos[1]];
                    node._stepId = step.id;
                    self.placedNodes.push(node);
                    self.graph.remove(shadow);
                    self.shadowNodes = [];
                    if (step.autoWire && step.autoWire.length) {
                        step.autoWire.forEach(function(w){
                            var pid = self.module.steps[w.fromStep - 1];
                            if (!pid) return;
                            var pNodes = self.placedNodes.filter(function(n){ return n._stepId === pid.id; });
                            if (pNodes.length) {
                                pNodes[0].connect(w.fromPort || 0, node, w.toPort || 0);
                            }
                        });
                    }
                    playTransformUp();
                    clearTimeout(self.idleTimer);
                    self._hideAutoBtn();
                    setTimeout(function(){ self._showStep(self.stepIndex + 1); }, 350);
                }
            }
        }
    };
};

StudioTutorial.prototype._uninstallHooks = function() {
    if (this._origOnNodeAdded !== null) this.graph.onNodeAdded = this._origOnNodeAdded;
    if (this._origOnConnectionChange !== null) this.graph.onConnectionChange = this._origOnConnectionChange;
};

StudioTutorial.prototype._startPulse = function() {
    var self = this;
    this._stopPulse();
    this._animFrame = window.requestAnimationFrame(function tick() {
        self.canvas.setDirty(true, true);
        if (self.active) self._animFrame = window.requestAnimationFrame(tick);
    });
};

StudioTutorial.prototype._stopPulse = function() {
    if (this._animFrame) { window.cancelAnimationFrame(this._animFrame); this._animFrame = null; }
};


// ============================================================
//  Global init — called after designer.js sets up graph + canvas
// ============================================================

var tutorial = null;

function initTutorial(graph, canvasEl) {
    tutorial = new StudioTutorial(graph, canvasEl);
    return tutorial;
}
