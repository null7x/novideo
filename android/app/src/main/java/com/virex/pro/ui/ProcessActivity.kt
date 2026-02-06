package com.virex.pro.ui

import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.net.toUri
import androidx.lifecycle.lifecycleScope
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import com.virex.pro.VirexApp
import com.virex.pro.data.ProcessingState
import com.virex.pro.data.ProcessingStatus
import com.virex.pro.databinding.ActivityProcessBinding
import java.io.File
import java.io.FileOutputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody

class ProcessActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_VIDEO_URI = "video_uri"
        const val EXTRA_TEMPLATE = "template"

        val TEMPLATE_NAMES =
                mapOf(
                        "tiktok" to "TikTok",
                        "reels" to "Instagram Reels",
                        "youtube" to "YouTube Shorts",
                        "clean" to "Чистое видео",
                        "watermark_trap" to "🛡️ Watermark-Trap",
                        "gaming" to "🎮 Gaming",
                        "vlog" to "📹 Vlog",
                        "cinematic" to "🎬 Cinematic",
                        "vintage" to "📼 Vintage",
                        "neon" to "💜 Neon",
                        "bw" to "⚫ Чёрно-белое",
                        "speed" to "⚡ Speed Edit",
                        "viral_4k" to "🔥 Viral 4K",
                        "viral_8k" to "💎 Viral 8K",
                        "viral_10k" to "👑 Viral 10K",
                        "viral_16k" to "🚀 Viral 16K",
                        "passport" to "🔐 Паспорт",
                        "passport_pro" to "🛡️ Паспорт PRO",
                        "viral_120fps" to "🎬 120FPS Smooth",
                        "viral_8k_120fps" to "💎 8K 120FPS",
                        "avatar_style" to "🌊 Avatar Style",
                        "aesthetic_hdr" to "✨ Aesthetic HDR",
                        "movie_quality" to "🎥 Movie Quality",
                        "ultra_viral" to "🔥 Ultra Viral"
                )
    }

    private lateinit var binding: ActivityProcessBinding
    private val app by lazy { VirexApp.instance }

    private var player: ExoPlayer? = null
    private var videoUri: Uri? = null
    private var template: String = "tiktok"
    private var outputFile: File? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityProcessBinding.inflate(layoutInflater)
        setContentView(binding.root)

        videoUri = intent.getStringExtra(EXTRA_VIDEO_URI)?.toUri()
        template = intent.getStringExtra(EXTRA_TEMPLATE) ?: "tiktok"

        if (videoUri == null) {
            Toast.makeText(this, "Видео не выбрано", Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        setupViews()
        showPreview()
    }

    private fun setupViews() {
        binding.tvTemplate.text = "🎬 ${TEMPLATE_NAMES[template] ?: template}"

        binding.btnProcess.setOnClickListener { startProcessing() }

        binding.btnCancel.setOnClickListener { finish() }

        binding.btnShare.setOnClickListener { shareVideo() }

        binding.btnSave.setOnClickListener { saveVideo() }

        // Кнопка опций
        binding.btnOptions.setOnClickListener {
            if (binding.optionsLayout.visibility == android.view.View.VISIBLE) {
                binding.optionsLayout.visibility = android.view.View.GONE
                binding.btnOptions.text = "⚙️ Опции"
            } else {
                binding.optionsLayout.visibility = android.view.View.VISIBLE
                binding.btnOptions.text = "✕ Скрыть"
            }
        }
    }

    private fun getTextOverlay(): String? {
        val text = binding.etTextOverlay.text?.toString()?.trim()
        return if (text.isNullOrEmpty()) null else text
    }

    private fun showPreview() {
        player =
                ExoPlayer.Builder(this).build().apply {
                    binding.playerView.player = this
                    setMediaItem(MediaItem.fromUri(videoUri!!))
                    prepare()
                }
    }

    private fun startProcessing() {
        updateState(ProcessingState(ProcessingStatus.UPLOADING, message = "Загрузка видео..."))

        lifecycleScope.launch {
            try {
                // Копируем видео во временный файл
                val tempFile = withContext(Dispatchers.IO) { copyUriToTempFile(videoUri!!) }

                updateState(ProcessingState(ProcessingStatus.PROCESSING, message = "Обработка..."))

                // Отправляем на сервер
                val requestFile = tempFile.asRequestBody("video/mp4".toMediaType())
                val videoPart =
                        MultipartBody.Part.createFormData("video", tempFile.name, requestFile)

                val response =
                        app.apiClient.api.processVideo(
                                userId = app.preferencesManager.userId.toString(),
                                token = app.preferencesManager.authToken ?: "",
                                video = videoPart,
                                template = MultipartBody.Part.createFormData("template", template),
                                text =
                                        getTextOverlay()?.let {
                                            MultipartBody.Part.createFormData("text", it)
                                        }
                        )

                // Удаляем временный входной файл
                tempFile.delete()

                if (response.isSuccessful) {
                    updateState(
                            ProcessingState(ProcessingStatus.DOWNLOADING, message = "Скачивание...")
                    )

                    // Сохраняем результат
                    outputFile =
                            withContext(Dispatchers.IO) {
                                val outFile =
                                        File(
                                                cacheDir,
                                                "virex_output_${System.currentTimeMillis()}.mp4"
                                        )
                                response.body()?.byteStream()?.use { input ->
                                    FileOutputStream(outFile).use { output -> input.copyTo(output) }
                                }
                                outFile
                            }

                    // Обновляем счётчик
                    app.preferencesManager.totalVideos++

                    updateState(
                            ProcessingState(
                                    status = ProcessingStatus.COMPLETED,
                                    outputPath = outputFile?.absolutePath,
                                    message = "Готово!"
                            )
                    )

                    // Показываем результат
                    showResult()
                } else {
                    val error = response.errorBody()?.string() ?: "Ошибка обработки"
                    updateState(ProcessingState(ProcessingStatus.ERROR, error = error))
                }
            } catch (e: Exception) {
                updateState(ProcessingState(ProcessingStatus.ERROR, error = e.message))
            }
        }
    }

    private fun updateState(state: ProcessingState) {
        runOnUiThread {
            when (state.status) {
                ProcessingStatus.IDLE -> {
                    binding.progressLayout.visibility = View.GONE
                    binding.resultLayout.visibility = View.GONE
                    binding.btnProcess.isEnabled = true
                    binding.btnProcess.text = "🚀 Обработать"
                }
                ProcessingStatus.UPLOADING -> {
                    binding.progressLayout.visibility = View.VISIBLE
                    binding.tvProgressStatus.text = "📤 Загрузка видео на сервер..."
                    binding.progressBar.isIndeterminate = true
                    binding.btnProcess.isEnabled = false
                    binding.btnProcess.text = "⏳ Загрузка..."
                    binding.resultLayout.visibility = View.GONE
                }
                ProcessingStatus.PROCESSING -> {
                    binding.progressLayout.visibility = View.VISIBLE
                    binding.tvProgressStatus.text =
                            "⚙️ Применяем эффекты...\n🎬 ${TEMPLATE_NAMES[template] ?: template}"
                    binding.progressBar.isIndeterminate = true
                    binding.btnProcess.isEnabled = false
                    binding.btnProcess.text = "⏳ Обработка..."
                    binding.resultLayout.visibility = View.GONE
                }
                ProcessingStatus.DOWNLOADING -> {
                    binding.progressLayout.visibility = View.VISIBLE
                    binding.tvProgressStatus.text = "📥 Скачивание готового видео..."
                    binding.progressBar.isIndeterminate = true
                    binding.btnProcess.isEnabled = false
                    binding.btnProcess.text = "⏳ Скачивание..."
                    binding.resultLayout.visibility = View.GONE
                }
                ProcessingStatus.COMPLETED -> {
                    binding.progressLayout.visibility = View.GONE
                    binding.resultLayout.visibility = View.VISIBLE
                    binding.btnProcess.isEnabled = true
                    binding.btnProcess.text = "🔄 Обработать ещё"
                    Toast.makeText(this, "✅ Готово! Видео обработано", Toast.LENGTH_SHORT).show()
                }
                ProcessingStatus.ERROR -> {
                    binding.progressLayout.visibility = View.GONE
                    binding.resultLayout.visibility = View.GONE
                    binding.btnProcess.isEnabled = true
                    binding.btnProcess.text = "🚀 Попробовать снова"
                    Toast.makeText(
                                    this,
                                    "❌ ${state.error ?: "Ошибка обработки"}",
                                    Toast.LENGTH_LONG
                            )
                            .show()
                }
            }
        }
    }

    private fun showResult() {
        outputFile?.let { file ->
            player?.release()
            player =
                    ExoPlayer.Builder(this).build().apply {
                        binding.playerView.player = this
                        setMediaItem(MediaItem.fromUri(Uri.fromFile(file)))
                        prepare()
                        play()
                    }
        }
    }

    private fun shareVideo() {
        outputFile?.let { file ->
            val uri =
                    androidx.core.content.FileProvider.getUriForFile(
                            this,
                            "$packageName.fileprovider",
                            file
                    )

            val intent =
                    android.content.Intent(android.content.Intent.ACTION_SEND).apply {
                        type = "video/mp4"
                        putExtra(android.content.Intent.EXTRA_STREAM, uri)
                        addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }

            startActivity(android.content.Intent.createChooser(intent, "Поделиться видео"))
        }
    }

    private fun saveVideo() {
        outputFile?.let { file ->
            // Копируем в галерею
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
                        file.inputStream().use { input -> input.copyTo(output) }
                    }
                    Toast.makeText(this, "Сохранено в галерею", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Toast.makeText(this, "Ошибка сохранения: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun copyUriToTempFile(uri: Uri): File {
        val tempFile = File(cacheDir, "temp_input_${System.currentTimeMillis()}.mp4")
        contentResolver.openInputStream(uri)?.use { input ->
            FileOutputStream(tempFile).use { output -> input.copyTo(output) }
        }
        return tempFile
    }

    override fun onPause() {
        super.onPause()
        player?.pause()
    }

    override fun onDestroy() {
        super.onDestroy()
        player?.release()
        player = null
    }
}
