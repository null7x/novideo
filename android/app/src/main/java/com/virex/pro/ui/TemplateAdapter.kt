package com.virex.pro.ui

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.card.MaterialCardView
import com.virex.pro.R
import com.virex.pro.data.Template

class TemplateAdapter(
        private val templates: List<Template>,
        private val isPremium: Boolean,
        private val onTemplateSelected: (Template) -> Unit
) : RecyclerView.Adapter<TemplateAdapter.ViewHolder>() {

    private var selectedPosition = -1

    class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val card: MaterialCardView = view.findViewById(R.id.cardTemplate)
        val icon: ImageView = view.findViewById(R.id.ivTemplateIcon)
        val name: TextView = view.findViewById(R.id.tvTemplateName)
        val description: TextView = view.findViewById(R.id.tvTemplateDescription)
        val premiumBadge: TextView = view.findViewById(R.id.tvPremiumBadge)
        val lockOverlay: View = view.findViewById(R.id.viewLockOverlay)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val view =
                LayoutInflater.from(parent.context).inflate(R.layout.item_template, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val template = templates[position]

        holder.name.text = template.name
        holder.description.text = template.description

        if (template.icon != 0) {
            holder.icon.setImageResource(template.icon)
        }

        // Premium badge и лок
        if (template.isPremium) {
            holder.premiumBadge.visibility = View.VISIBLE
            holder.premiumBadge.text = "PRO"
            if (isPremium) {
                holder.lockOverlay.visibility = View.GONE
                holder.icon.alpha = 1.0f
            } else {
                holder.lockOverlay.visibility = View.VISIBLE
                holder.icon.alpha = 0.5f
            }
        } else {
            holder.premiumBadge.visibility = View.GONE
            holder.lockOverlay.visibility = View.GONE
            holder.icon.alpha = 1.0f
        }

        // Selection state
        holder.card.isSelected = position == selectedPosition
        holder.card.strokeWidth = if (position == selectedPosition) 4 else 0

        holder.card.setOnClickListener {
            if (template.isPremium && !isPremium) {
                Toast.makeText(
                                holder.itemView.context,
                                "⭐ Этот шаблон доступен только для Premium",
                                Toast.LENGTH_SHORT
                        )
                        .show()
                return@setOnClickListener
            }

            val oldPosition = selectedPosition
            selectedPosition = holder.adapterPosition
            if (oldPosition >= 0) notifyItemChanged(oldPosition)
            notifyItemChanged(selectedPosition)
            onTemplateSelected(template)
        }
    }

    override fun getItemCount() = templates.size

    fun updatePremiumStatus(isPremium: Boolean) {
        // Перерисовать все элементы
        notifyDataSetChanged()
    }
}
