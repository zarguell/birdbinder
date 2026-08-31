/**
 * Shared rarity configuration — single source of truth for tier colors and
 * labels. Previously defined three different ways across four files.
 */

export interface RarityStyle {
	bg: string;
	text: string;
	label: string;
	border: string;
	glow: string;
}

export const rarityConfig: Record<string, RarityStyle> = {
	common: { bg: 'bg-gray-600', text: 'text-gray-200', label: 'Common', border: 'border-gray-500/50', glow: '' },
	uncommon: { bg: 'bg-green-700', text: 'text-green-100', label: 'Uncommon', border: 'border-green-500/60', glow: 'hover:shadow-green-500/20' },
	rare: { bg: 'bg-blue-700', text: 'text-blue-100', label: 'Rare', border: 'border-blue-400/60', glow: 'hover:shadow-blue-500/25' },
	epic: { bg: 'bg-purple-700', text: 'text-purple-100', label: 'Epic', border: 'border-purple-400/60', glow: 'hover:shadow-purple-500/25' },
	legendary: { bg: 'bg-amber-600', text: 'text-amber-100', label: 'Legendary', border: 'border-amber-400/70', glow: 'hover:shadow-amber-400/30' }
};

export function getRarityStyle(tier: string | null | undefined): RarityStyle {
	return rarityConfig[tier?.toLowerCase() ?? ''] ?? rarityConfig.common;
}

/** Badge classes for the pill-style rarity chip used on detail pages. */
export function rarityBadgeClass(tier: string | null | undefined): string {
	const style = getRarityStyle(tier);
	return `${style.border} ${style.text}`;
}

/** Plain text color for rarity labels in prose contexts. */
export function rarityTextColor(tier: string | null | undefined): string {
	switch (tier?.toLowerCase()) {
		case 'uncommon':
			return 'text-green-400';
		case 'rare':
			return 'text-blue-400';
		case 'epic':
			return 'text-purple-400';
		case 'legendary':
			return 'text-amber-400';
		default:
			return 'text-gray-400';
	}
}
