/**
 * Shared formatting helpers. Previously copy-pasted (with drift) across
 * seven pages — import from here instead.
 */

export type DateStyle = 'datetime' | 'datetime-long' | 'date' | 'date-long' | 'month-year';

const PRESETS: Record<DateStyle, Intl.DateTimeFormatOptions> = {
	// "Jan 5, 2:31 PM"
	datetime: { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' },
	// "Sat, Jan 5, 2025, 2:31 PM"
	'datetime-long': {
		weekday: 'short',
		month: 'short',
		day: 'numeric',
		year: 'numeric',
		hour: '2-digit',
		minute: '2-digit'
	},
	// "Jan 5, 2025"
	date: { month: 'short', day: 'numeric', year: 'numeric' },
	// "January 5, 2025"
	'date-long': { year: 'numeric', month: 'long', day: 'numeric' },
	// "January 2025"
	'month-year': { month: 'long', year: 'numeric' }
};

export function formatDate(dateStr: string | null | undefined, style: DateStyle = 'date'): string {
	if (!dateStr) return '—';
	try {
		const d = new Date(dateStr);
		if (isNaN(d.getTime())) return dateStr;
		return d.toLocaleDateString('en-US', PRESETS[style]);
	} catch {
		return dateStr;
	}
}
