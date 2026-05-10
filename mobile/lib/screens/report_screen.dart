import 'package:flutter/material.dart';
import '../services/api.dart';

class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key});
  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  final _tickerCtrl = TextEditingController();
  String _formType = '10-Q';
  bool _loading = false;
  Map<String, dynamic>? _result;
  String? _error;

  Future<void> _analyze() async {
    final t = _tickerCtrl.text.trim().toUpperCase();
    if (t.isEmpty) return;
    setState(() { _loading = true; _result = null; _error = null; });
    try {
      final r = await Api.analyzeReport(t, formType: _formType);
      setState(() => _result = r);
    } catch (e) {
      setState(() => _error = 'לא נמצא דוח או שגיאה בניתוח');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('🤖 ניתוח דוחות AI')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(children: [
              Expanded(
                child: TextField(
                  controller: _tickerCtrl,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(
                    labelText: 'סימול מניה',
                    hintText: 'AAPL, NVDA, TSLA...',
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: (_) => _analyze(),
                ),
              ),
              const SizedBox(width: 8),
              DropdownButton<String>(
                value: _formType,
                items: const [
                  DropdownMenuItem(value: '10-Q', child: Text('10-Q רבעוני')),
                  DropdownMenuItem(value: '10-K', child: Text('10-K שנתי')),
                  DropdownMenuItem(value: '8-K', child: Text('8-K אירוע')),
                ],
                onChanged: (v) => setState(() => _formType = v ?? '10-Q'),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: _loading ? null : _analyze,
                child: const Text('נתח'),
              ),
            ]),
            const SizedBox(height: 16),
            if (_loading) const Center(child: Column(children: [
              CircularProgressIndicator(),
              SizedBox(height: 12),
              Text('מוריד דוח מ-SEC EDGAR ומנתח עם AI...', style: TextStyle(color: Colors.grey)),
            ])),
            if (_error != null) Text(_error!, style: const TextStyle(color: Colors.red)),
            if (_result != null) Expanded(child: _ReportCard(data: _result!)),
          ],
        ),
      ),
    );
  }
}

class _ReportCard extends StatelessWidget {
  final Map<String, dynamic> data;
  const _ReportCard({required this.data});

  @override
  Widget build(BuildContext context) {
    final sentiment = data['sentiment'] as String? ?? 'neutral';
    final sentimentColor = sentiment == 'bullish' ? Colors.green
        : sentiment == 'bearish' ? Colors.red : Colors.orange;
    final sentimentIcon = sentiment == 'bullish' ? '📈' : sentiment == 'bearish' ? '📉' : '➡️';

    return SingleChildScrollView(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        // Header
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: sentimentColor.withOpacity(.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: sentimentColor.withOpacity(.3)),
          ),
          child: Row(children: [
            Text(sentimentIcon, style: const TextStyle(fontSize: 28)),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${data['company'] ?? ''} (${data['ticker'] ?? ''})',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              Text('${data['report_type']} · ${data['period']}',
                  style: TextStyle(color: Colors.grey[600], fontSize: 13)),
            ])),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(color: sentimentColor, borderRadius: BorderRadius.circular(20)),
              child: Text(sentiment.toUpperCase(), style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
            ),
          ]),
        ),
        const SizedBox(height: 14),

        // Summary
        _Section(title: '📋 סיכום', content: data['summary'] ?? ''),

        // Numbers
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: _MetricBox(label: 'הכנסות', value: _fmt(data['revenue']), sub: _chg(data['revenue']))),
          const SizedBox(width: 8),
          Expanded(child: _MetricBox(label: 'רווח נקי', value: _fmt(data['net_income']), sub: _chg(data['net_income']))),
          const SizedBox(width: 8),
          Expanded(child: _MetricBox(label: 'EPS', value: '\$${data['eps']?['value'] ?? '—'}', sub: data['eps']?['vs_estimate'] != null ? 'vs \$${data['eps']['vs_estimate']}' : '')),
        ]),
        const SizedBox(height: 14),

        // Highlights
        if ((data['key_highlights'] as List?)?.isNotEmpty == true)
          _BulletSection(title: '✅ נקודות מפתח', items: List<String>.from(data['key_highlights'])),
        const SizedBox(height: 10),

        // Risks
        if ((data['risks'] as List?)?.isNotEmpty == true)
          _BulletSection(title: '⚠️ סיכונים', items: List<String>.from(data['risks']), color: Colors.orange),
        const SizedBox(height: 10),

        // Outlook
        if (data['outlook'] != null)
          _Section(title: '🔭 תחזית הנהלה', content: data['outlook']),
        const SizedBox(height: 20),
      ]),
    );
  }

  String _fmt(dynamic val) {
    if (val == null || val['value'] == null) return '—';
    final v = (val['value'] as num).toDouble();
    if (v.abs() >= 1e9) return '\$${(v / 1e9).toStringAsFixed(1)}B';
    if (v.abs() >= 1e6) return '\$${(v / 1e6).toStringAsFixed(0)}M';
    return '\$${v.toStringAsFixed(0)}';
  }

  String _chg(dynamic val) {
    if (val == null || val['change_pct'] == null) return '';
    final pct = (val['change_pct'] as num).toDouble();
    return '${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(1)}% YoY';
  }
}

class _Section extends StatelessWidget {
  final String title, content;
  const _Section({required this.title, required this.content});
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
    const SizedBox(height: 6),
    Text(content, style: TextStyle(color: Colors.grey[700], fontSize: 13, height: 1.5)),
  ]);
}

class _BulletSection extends StatelessWidget {
  final String title;
  final List<String> items;
  final Color? color;
  const _BulletSection({required this.title, required this.items, this.color});
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
    const SizedBox(height: 6),
    ...items.map((i) => Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('• ', style: TextStyle(color: color ?? Colors.green, fontWeight: FontWeight.bold)),
        Expanded(child: Text(i, style: TextStyle(fontSize: 13, color: Colors.grey[700]))),
      ]),
    )),
  ]);
}

class _MetricBox extends StatelessWidget {
  final String label, value, sub;
  const _MetricBox({required this.label, required this.value, required this.sub});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(10),
    decoration: BoxDecoration(
      border: Border.all(color: Colors.grey.withOpacity(.2)),
      borderRadius: BorderRadius.circular(10),
    ),
    child: Column(children: [
      Text(label, style: TextStyle(fontSize: 11, color: Colors.grey[600])),
      const SizedBox(height: 4),
      Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
      if (sub.isNotEmpty) Text(sub, style: TextStyle(fontSize: 10, color: Colors.grey[500])),
    ]),
  );
}
