package com.virex.pro.ui

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.card.MaterialCardView
import com.virex.pro.R
import com.virex.pro.databinding.ActivityHistoryBinding
import java.io.File
import java.text.SimpleDateFormat
import java.util.*

class HistoryActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHistoryBinding
    private val videoFiles = mutableListOf<VideoFile>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityHistoryBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupViews()
        loadVideos()
    }

    private fun setupViews() {
        binding.toolbar.setNavigationOnClickListener { finish() }

        binding.rvHistory.layoutManager = LinearLayoutManager(this)

        binding.btnClearAll.setOnClickListener {
            android.app.AlertDialog.Builder(this)
                    .setTitle("Очистить историю?")
                    .setMessage("Все обработанные видео будут удалены из кэша")
                    .setPositiveButton("Удалить") { _, _ -> clearAllVideos() }
                    .setNegativeButton("Отмена", null)
                    .show()
        }
    }

    private fun loadVideos() {
        videoFiles.clear()

        // Загружаем видео из кэша
        cacheDir.listFiles()
                ?.filter {
                    it.isFile && it.name.startsWith("virex_output_") && it.name.endsWith(".mp4")
                }
                ?.sortedByDescending { it.lastModified() }
                ?.forEach { file ->
                    videoFiles.add(
                            VideoFile(
                                    file = file,
                                    name = "Видео ${videoFiles.size + 1}",
                                    date = Date(file.lastModified()),
                                    size = file.length()
                            )
                    )
                }

        updateUI()
    }

    private fun updateUI() {
        if (videoFiles.isEmpty()) {
            binding.emptyLayout.visibility = View.VISIBLE
            binding.rvHistory.visibility = View.GONE
            binding.btnClearAll.visibility = View.GONE
        } else {
            binding.emptyLayout.visibility = View.GONE
            binding.rvHistory.visibility = View.VISIBLE
            binding.btnClearAll.visibility = View.VISIBLE
            binding.rvHistory.adapter =
                    HistoryAdapter(
                            videoFiles,
                            onShare = { shareVideo(it) },
                            onDelete = { deleteVideo(it) },
                            onSave = { saveToGallery(it) }
                    )
        }

        binding.tvTotalCount.text = "Всего: ${videoFiles.size} видео"
    }

    private fun shareVideo(videoFile: VideoFile) {
        try {
            val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", videoFile.file)
            val intent =
                    Intent(Intent.ACTION_SEND).apply {
                        type = "video/mp4"
                        putExtra(Intent.EXTRA_STREAM, uri)
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }
            startActivity(Intent.createChooser(intent, "Поделиться видео"))
        } catch (e: Exception) {
            Toast.makeText(this, "Ошибка: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun deleteVideo(videoFile: VideoFile) {
        android.app.AlertDialog.Builder(this)
                .setTitle("Удалить видео?")
                .setPositiveButton("Удалить") { _, _ ->
                    if (videoFile.file.delete()) {
                        videoFiles.remove(videoFile)
                        updateUI()
                        Toast.makeText(this, "Видео удалено", Toast.LENGTH_SHORT).show()
                    }
                }
                .setNegativeButton("Отмена", null)
                .show()
    }

    private fun saveToGallery(videoFile: VideoFile) {
        val resolver = contentResolver
        val contentValues =
                android.content.ContentValues().apply {
                    put(
                            android.provider.MediaStore.Video.Media.DISPLAY_NAME,
                            "virex_${System.currentTimeMillis()}.mp4"
                    )
                    put(android.provider.MediaStore.Video.Media.MIME_TYPE, "video/mp4")
                    put(android.provider.MediaStore.Video.Media.RELATIVE_PATH, "Movies/Virex")
                }

        try {
            val uri =
                    resolver.insert(
                            android.provider.MediaStore.Video.Media.EXTERNAL_CONTENT_URI,
                            contentValues
                    )
            uri?.let { destUri ->
                resolver.openOutputStream(destUri)?.use { output ->
                    videoFile.file.inputStream().use { input -> input.copyTo(output) }
                }
                Toast.makeText(this, "✅ Сохранено в галерею", Toast.LENGTH_SHORT).show()
            }
        } catch (e: Exception) {
            Toast.makeText(this, "❌ Ошибка: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun clearAllVideos() {
        videoFiles.forEach { it.file.delete() }
        videoFiles.clear()
        updateUI()
        Toast.makeText(this, "История очищена", Toast.LENGTH_SHORT).show()
    }

    data class VideoFile(val file: File, val name: String, val date: Date, val size: Long)

    class HistoryAdapter(
            private val videos: List<VideoFile>,
            private val onShare: (VideoFile) -> Unit,
            private val onDelete: (VideoFile) -> Unit,
            private val onSave: (VideoFile) -> Unit
    ) : RecyclerView.Adapter<HistoryAdapter.ViewHolder>() {

        class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
            val card: MaterialCardView = view.findViewById(R.id.cardVideo)
            val tvName: TextView = view.findViewById(R.id.tvVideoName)
            val tvDate: TextView = view.findViewById(R.id.tvVideoDate)
            val tvSize: TextView = view.findViewById(R.id.tvVideoSize)
            val btnShare: ImageView = view.findViewById(R.id.btnShare)
            val btnSave: ImageView = view.findViewById(R.id.btnSave)
            val btnDelete: ImageView = view.findViewById(R.id.btnDelete)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
            val view =
                    LayoutInflater.from(parent.context)
                            .inflate(R.layout.item_history, parent, false)
            return ViewHolder(view)
        }

        override fun onBindViewHolder(holder: ViewHolder, position: Int) {
            val video = videos[position]

            holder.tvName.text = video.name
            holder.tvDate.text =
                    SimpleDateFormat("dd.MM.yyyy HH:mm", Locale.getDefault()).format(video.date)
            holder.tvSize.text = formatSize(video.size)

            holder.btnShare.setOnClickListener { onShare(video) }
            holder.btnSave.setOnClickListener { onSave(video) }
            holder.btnDelete.setOnClickListener { onDelete(video) }
        }

        override fun getItemCount() = videos.size

        private fun formatSize(size: Long): String {
            return when {
                size < 1024 -> "$size B"
                size < 1024 * 1024 -> "${size / 1024} KB"
                else -> "${size / 1024 / 1024} MB"
            }
        }
    }
}
