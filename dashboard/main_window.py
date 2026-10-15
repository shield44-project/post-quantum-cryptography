from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSpinBox,
    QDoubleSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from dashboard.services import PQAIService
from dashboard.workers import TaskWorker


def _path_row(
    label: str,
    button_text: str,
    default: str = "",
    mode: str = "dir",
) -> tuple[QWidget, QLineEdit]:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)

    line_edit = QLineEdit(default)
    browse_button = QPushButton(button_text)

    def choose_path() -> None:
        if mode == "dir":
            selected = QFileDialog.getExistingDirectory(widget, f"Select {label}", line_edit.text() or str(Path.home()))
        elif mode == "save":
            selected, _ = QFileDialog.getSaveFileName(widget, f"Select {label}", line_edit.text() or str(Path.home()))
        else:
            selected, _ = QFileDialog.getOpenFileName(widget, f"Select {label}", line_edit.text() or str(Path.home()))

        if selected:
            line_edit.setText(selected)

    browse_button.clicked.connect(choose_path)
    layout.addWidget(line_edit, 1)
    layout.addWidget(browse_button)
    return widget, line_edit


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.service = PQAIService()
        self._workers: list[TaskWorker] = []
        self._action_buttons: list[QPushButton] = []
        self.setWindowTitle("PQ-AI Provenance Dashboard")
        self.resize(1440, 920)
        self._build_ui()
        self._apply_style()

    def _apply_style(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyle("Fusion")

        self.setStyleSheet(
            """
            QMainWindow {
                background: #0f172a;
                color: #e2e8f0;
            }
            QLabel, QGroupBox, QTabWidget::pane, QPlainTextEdit, QTextBrowser, QLineEdit, QSpinBox, QDoubleSpinBox {
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 10px;
                margin-top: 12px;
                padding: 8px;
                background: #111827;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #f8fafc;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                border-radius: 10px;
                background: #111827;
            }
            QTabBar::tab {
                background: #1f2937;
                color: #cbd5e1;
                padding: 10px 16px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #2563eb;
                color: white;
            }
            QPushButton {
                background: #2563eb;
                color: white;
                border: none;
                padding: 8px 14px;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QPushButton:disabled {
                background: #475569;
                color: #cbd5e1;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextBrowser {
                background: #0b1120;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px;
            }
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 8px;
                text-align: center;
                background: #0b1120;
                color: #e2e8f0;
                height: 18px;
            }
            QProgressBar::chunk {
                background: #22c55e;
                border-radius: 8px;
            }
            """
        )

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setSpacing(12)

        header = QLabel(
            "PQ-AI Provenance combines dataset hashing, ML-DSA signing, model training, watermarking, and tamper analysis in one local desktop workflow."
        )
        header.setWordWrap(True)
        header.setStyleSheet("font-size: 15px; font-weight: 600; color: #f8fafc;")

        workflow = QTextBrowser()
        workflow.setMinimumHeight(110)
        workflow.setText(
            "<b>Workflow</b><br>1. Select a dataset.<br>2. Hash it with SHA-256.<br>3. Create and sign a provenance manifest.<br>4. Train or load a model.<br>5. Add or check a watermark.<br>6. Generate tampered datasets and robustness reports.<br>7. Export the result trail for review."
        )

        root_layout.addWidget(header)
        root_layout.addWidget(workflow)
        root_layout.addWidget(self._build_workspace_group())
        root_layout.addWidget(self._build_tabs())
        root_layout.addWidget(self._build_log_panel())

        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")

    def _build_workspace_group(self) -> QGroupBox:
        group = QGroupBox("Workspace")
        layout = QGridLayout(group)

        defaults = self.service.paths

        data_row, self.data_dir_edit = _path_row("Data Directory", "Browse", str(defaults.data_dir), "dir")
        dataset_row, self.dataset_edit = _path_row("Dataset Path", "Browse", str(defaults.data_dir), "dir")
        results_row, self.results_edit = _path_row("Results Directory", "Browse", str(defaults.results_dir), "dir")
        keys_row, self.keys_edit = _path_row("Keys Directory", "Browse", str(defaults.keys_dir), "dir")
        preferred_model = Path("model/best_resnet18.pth")
        model_default = preferred_model if preferred_model.exists() else (defaults.models_dir / "resnet18_original.pth")
        model_input_row, self.model_input_edit = _path_row("Model Path", "Browse", str(model_default), "open")
        model_output_row, self.model_output_edit = _path_row("Watermarked Model Path", "Browse", str(defaults.models_dir / "resnet18_watermarked.pth"), "save")
        tampered_row, self.tampered_edit = _path_row("Tampered Dataset Output", "Browse", str(defaults.data_dir / "tampered" / "cifar_10_percent.pt"), "save")

        self.dataset_name_edit = QLineEdit("CIFAR-10")
        self.model_name_edit = QLineEdit("ResNet-18")
        self.watermark_edit = QLineEdit("PQAIP-RVCE-2026-001")

        layout.addWidget(QLabel("Data directory"), 0, 0)
        layout.addWidget(data_row, 0, 1)
        layout.addWidget(QLabel("Dataset path"), 1, 0)
        layout.addWidget(dataset_row, 1, 1)
        layout.addWidget(QLabel("Results directory"), 0, 2)
        layout.addWidget(results_row, 0, 3)
        layout.addWidget(QLabel("Keys directory"), 1, 2)
        layout.addWidget(keys_row, 1, 3)
        layout.addWidget(QLabel("Dataset name"), 2, 0)
        layout.addWidget(self.dataset_name_edit, 2, 1)
        layout.addWidget(QLabel("Model name"), 2, 2)
        layout.addWidget(self.model_name_edit, 2, 3)
        layout.addWidget(QLabel("Model input"), 3, 0)
        layout.addWidget(model_input_row, 3, 1)
        layout.addWidget(QLabel("Model output"), 3, 2)
        layout.addWidget(model_output_row, 3, 3)
        layout.addWidget(QLabel("Watermark text"), 4, 0)
        layout.addWidget(self.watermark_edit, 4, 1)
        layout.addWidget(QLabel("Tampered dataset output"), 4, 2)
        layout.addWidget(tampered_row, 4, 3)

        return group

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.addTab(self._build_provenance_tab(), "Dataset & Crypto")
        tabs.addTab(self._build_model_tab(), "Model & Watermark")
        tabs.addTab(self._build_image_test_tab(), "Image Test")
        tabs.addTab(self._build_experiments_tab(), "Experiments")
        tabs.addTab(self._build_overview_tab(), "Process")
        return tabs

    def _build_provenance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        self.manifest_output_edit = QLineEdit(str(self.service.paths.results_dir))
        form.addRow("Manifest output", self.manifest_output_edit)

        button_row = QHBoxLayout()
        hash_button = QPushButton("Hash Dataset")
        manifest_button = QPushButton("Create Signed Manifest")
        verify_button = QPushButton("Verify Manifest")
        key_button = QPushButton("Generate Keys")

        self._action_buttons.extend([hash_button, manifest_button, verify_button, key_button])

        hash_button.clicked.connect(lambda: self._run_task("Hash dataset", self._hash_dataset))
        manifest_button.clicked.connect(lambda: self._run_task("Create manifest", self._create_manifest))
        verify_button.clicked.connect(lambda: self._run_task("Verify manifest", self._verify_manifest))
        key_button.clicked.connect(lambda: self._run_task("Generate ML-DSA keys", self._generate_keys))

        for button in [hash_button, manifest_button, verify_button, key_button]:
            button_row.addWidget(button)

        self.provenance_summary = QTextBrowser()
        self.provenance_summary.setPlaceholderText("Dataset hashing and manifest details will appear here.")

        layout.addLayout(form)
        layout.addLayout(button_row)
        layout.addWidget(self.provenance_summary, 1)
        return widget

    def _build_model_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(1, 100)
        self.epochs_spin.setValue(1)
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(8, 512)
        self.batch_spin.setValue(64)
        self.lr_spin = QDoubleSpinBox()
        self.lr_spin.setRange(0.000001, 1.0)
        self.lr_spin.setDecimals(6)
        self.lr_spin.setSingleStep(0.0001)
        self.lr_spin.setValue(0.001)
        self.lr_spin.setDecimals(6)

        form.addRow("Epochs", self.epochs_spin)
        form.addRow("Batch size", self.batch_spin)
        form.addRow("Learning rate", self.lr_spin)

        buttons = QHBoxLayout()
        train_button = QPushButton("Train Baseline")
        evaluate_button = QPushButton("Evaluate Model")
        watermark_button = QPushButton("Embed Watermark")
        check_button = QPushButton("Check Watermark")

        self._action_buttons.extend([train_button, evaluate_button, watermark_button, check_button])

        train_button.clicked.connect(lambda: self._run_task("Train model", self._train_model))
        evaluate_button.clicked.connect(lambda: self._run_task("Evaluate model", self._evaluate_model))
        watermark_button.clicked.connect(lambda: self._run_task("Embed watermark", self._embed_watermark))
        check_button.clicked.connect(lambda: self._run_task("Check watermark", self._check_watermark))

        for button in [train_button, evaluate_button, watermark_button, check_button]:
            buttons.addWidget(button)

        self.model_summary = QTextBrowser()
        self.model_summary.setPlaceholderText("Model training and watermark results will appear here.")

        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.model_summary, 1)
        return widget

    def _build_image_test_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        default_model = Path("model/best_resnet18.pth")
        self.test_model_edit = QLineEdit(
            str(default_model.resolve()) if default_model.exists() else self.model_input_edit.text()
        )
        self.test_image_edit = QLineEdit()
        self.test_batch_edit = QLineEdit()
        self.test_topk_spin = QSpinBox()
        self.test_topk_spin.setRange(1, 5)
        self.test_topk_spin.setValue(3)
        self.test_sample_spin = QSpinBox()
        self.test_sample_spin.setRange(0, 49999)
        self.test_sample_spin.setValue(0)

        form.addRow("Model path", self.test_model_edit)
        form.addRow("Image path", self.test_image_edit)
        form.addRow("Image folder", self.test_batch_edit)
        form.addRow("Top-k predictions", self.test_topk_spin)
        form.addRow("CIFAR-10 sample index", self.test_sample_spin)

        buttons = QHBoxLayout()
        browse_image_button = QPushButton("Browse Image")
        browse_folder_button = QPushButton("Browse Folder")
        predict_button = QPushButton("Predict Image")
        sample_button = QPushButton("Test CIFAR-10 Sample")
        batch_button = QPushButton("Predict Folder")

        self._action_buttons.extend([browse_image_button, browse_folder_button, predict_button, sample_button, batch_button])

        def choose_image() -> None:
            selected, _ = QFileDialog.getOpenFileName(
                self,
                "Select Image",
                self.test_image_edit.text() or str(self.service.paths.data_dir),
                "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
            )
            if selected:
                self.test_image_edit.setText(selected)
                self._show_image_preview(selected)

        browse_image_button.clicked.connect(choose_image)
        def choose_folder() -> None:
            selected = QFileDialog.getExistingDirectory(
                self,
                "Select Image Folder",
                self.test_batch_edit.text() or str(self.service.paths.data_dir),
            )
            if selected:
                self.test_batch_edit.setText(selected)

        browse_folder_button.clicked.connect(choose_folder)
        predict_button.clicked.connect(lambda: self._run_task("Predict image", self._predict_image))
        sample_button.clicked.connect(lambda: self._run_task("Test CIFAR-10 sample", self._predict_sample))
        batch_button.clicked.connect(lambda: self._run_task("Predict image batch", self._predict_batch))

        for button in [browse_image_button, browse_folder_button, predict_button, sample_button, batch_button]:
            buttons.addWidget(button)

        self.image_preview = QLabel("Image preview")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumHeight(260)
        self.image_preview.setStyleSheet(
            "border: 1px dashed #475569; border-radius: 10px; color: #94a3b8; background: #0b1120;"
        )

        self.image_summary = QTextBrowser()
        self.image_summary.setPlaceholderText("Predictions and confidence scores will appear here.")

        self.batch_results = QTableWidget(0, 5)
        self.batch_results.setHorizontalHeaderLabels(["File", "Predicted", "Confidence", "Status", "Top-k"])
        self.batch_results.horizontalHeader().setStretchLastSection(True)

        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.image_preview)
        layout.addWidget(self.image_summary, 1)
        layout.addWidget(self.batch_results, 1)
        return widget

    def _build_experiments_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        self.tamper_spin = QDoubleSpinBox()
        self.tamper_spin.setRange(0.1, 100.0)
        self.tamper_spin.setDecimals(1)
        self.tamper_spin.setValue(10.0)
        self.robust_model_edit = QLineEdit(self.model_input_edit.text())
        self.robust_watermark_edit = QLineEdit(self.watermark_edit.text())

        form.addRow("Tamper percentage", self.tamper_spin)
        form.addRow("Robustness model", self.robust_model_edit)
        form.addRow("Robustness watermark", self.robust_watermark_edit)

        buttons = QHBoxLayout()
        tamper_button = QPushButton("Create Tampered Dataset")
        robustness_button = QPushButton("Run Robustness Test")
        benchmark_button = QPushButton("Run ML-DSA Benchmark")

        self._action_buttons.extend([tamper_button, robustness_button, benchmark_button])

        tamper_button.clicked.connect(lambda: self._run_task("Create tampered dataset", self._create_tampered_dataset))
        robustness_button.clicked.connect(lambda: self._run_task("Run robustness test", self._run_robustness))
        benchmark_button.clicked.connect(lambda: self._run_task("Benchmark ML-DSA", self._benchmark_crypto))

        for button in [tamper_button, robustness_button, benchmark_button]:
            buttons.addWidget(button)

        self.experiment_summary = QTextBrowser()
        self.experiment_summary.setPlaceholderText("Tampering and robustness results will appear here.")

        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.experiment_summary, 1)
        return widget

    def _build_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        overview = QTextBrowser()
        overview.setHtml(
            """
            <h3>Process Overview</h3>
            <ol>
              <li>Select a dataset and output folders.</li>
              <li>Hash the dataset and create a provenance manifest.</li>
              <li>Generate ML-DSA keys, sign the manifest, and verify it.</li>
              <li>Train a baseline model or load an existing checkpoint.</li>
              <li>Embed and check the model watermark.</li>
              <li>Create tampered datasets and run robustness tests.</li>
              <li>Review the logs and export the outputs from the results directory.</li>
            </ol>
            <p>This desktop shell is local-first and keeps long-running work off the UI thread.</p>
            """
        )
        layout.addWidget(overview)
        return widget

    def _build_log_panel(self) -> QGroupBox:
        group = QGroupBox("Activity Log")
        layout = QVBoxLayout(group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(180)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.log_view)
        layout.addWidget(self.progress)
        return group

    def _run_task(self, title: str, func, *args, **kwargs) -> None:
        worker = TaskWorker(title, func, *args, **kwargs)
        worker.started_task.connect(self._task_started)
        worker.log_message.connect(self._append_log)
        worker.completed.connect(lambda result: self._task_completed(title, result))
        worker.failed.connect(lambda error: self._task_failed(title, error))
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker: TaskWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        if self._workers:
            return

        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self._set_actions_enabled(True)
        self.statusBar().showMessage("Ready")

    def _task_started(self, title: str) -> None:
        self.progress.setRange(0, 0)
        self.statusBar().showMessage(f"Running: {title}")
        self._set_actions_enabled(False)
        self._append_log(f"\n=== {title} ===")

    def _task_completed(self, title: str, result) -> None:
        message = json.dumps(result, indent=2, default=str) if isinstance(result, dict) else str(result)
        self._append_log(f"Completed {title}")
        self._update_summary(title, message)

    def _task_failed(self, title: str, error: str) -> None:
        self._append_log(f"Task failed: {title}\n{error}")
        QMessageBox.critical(self, f"{title} failed", error)

    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message.rstrip())

    def _show_image_preview(self, image_path: str | Path) -> None:
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self.image_preview.setText("Unable to preview image")
            return

        self.image_preview.setPixmap(
            pixmap.scaled(360, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in self._action_buttons:
            button.setEnabled(enabled)

    def _update_summary(self, title: str, message: str) -> None:
        target = self.provenance_summary
        if "model" in title.lower() or "watermark" in title.lower():
            target = self.model_summary
        elif "tamper" in title.lower() or "robust" in title.lower() or "benchmark" in title.lower():
            target = self.experiment_summary
        elif "predict" in title.lower() or "sample" in title.lower() or "image" in title.lower():
            target = self.image_summary

        target.setPlainText(message)

    def _hash_dataset(self) -> dict[str, object]:
        dataset_path = self.dataset_edit.text().strip()
        dataset = Path(dataset_path)
        if not dataset.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {dataset}")

        dataset_hash, file_count = self.service._dataset_hash(dataset)
        result = {
            "dataset_path": str(dataset.resolve()),
            "dataset_hash": dataset_hash,
            "dataset_file_count": file_count,
        }
        self.provenance_summary.setPlainText(json.dumps(result, indent=2))
        return result

    def _create_manifest(self) -> dict[str, object]:
        return self.service.create_manifest(
            dataset_name=self.dataset_name_edit.text().strip(),
            dataset_path=self.dataset_edit.text().strip(),
            model_name=self.model_name_edit.text().strip(),
            watermark_id=self.watermark_edit.text().strip(),
            output_dir=self.manifest_output_edit.text().strip(),
        )

    def _verify_manifest(self) -> dict[str, object]:
        manifest_path = Path(self.manifest_output_edit.text().strip()) / "manifest.json"
        signature_path = Path(self.manifest_output_edit.text().strip()) / "manifest.sig"
        valid = self.service.verify_manifest(manifest_path, signature_path)
        return {"manifest_path": str(manifest_path), "signature_path": str(signature_path), "valid": valid}

    def _generate_keys(self) -> dict[str, object]:
        self.service.ensure_keys()
        return {"keys_dir": str(self.service.paths.keys_dir)}

    def _train_model(self) -> dict[str, object]:
        return self.service.train_model(
            data_root=self.data_dir_edit.text().strip(),
            epochs=self.epochs_spin.value(),
            batch_size=self.batch_spin.value(),
            learning_rate=self.lr_spin.value(),
            output_path=self.model_input_edit.text().strip(),
        )

    def _evaluate_model(self) -> dict[str, object]:
        return self.service.evaluate_model(
            model_path=self.model_input_edit.text().strip(),
            data_root=self.data_dir_edit.text().strip(),
            batch_size=self.batch_spin.value(),
        )

    def _embed_watermark(self) -> dict[str, object]:
        return self.service.embed_watermark(
            model_path=self.model_input_edit.text().strip(),
            watermark_text=self.watermark_edit.text().strip(),
            output_path=self.model_output_edit.text().strip(),
        )

    def _check_watermark(self) -> dict[str, object]:
        return self.service.check_watermark(
            model_path=self.model_output_edit.text().strip(),
            watermark_text=self.watermark_edit.text().strip(),
        )

    def _create_tampered_dataset(self) -> dict[str, object]:
        return self.service.create_tampered_dataset(
            percentage=self.tamper_spin.value(),
            output_path=self.tampered_edit.text().strip(),
            data_root=self.data_dir_edit.text().strip(),
        )

    def _run_robustness(self) -> dict[str, object]:
        return self.service.run_robustness_test(
            model_path=self.robust_model_edit.text().strip(),
            watermark_text=self.robust_watermark_edit.text().strip(),
        )

    def _benchmark_crypto(self) -> dict[str, object]:
        return self.service.benchmark_signature()

    def _predict_image(self) -> dict[str, object]:
        image_path = self.test_image_edit.text().strip()
        if not image_path:
            raise ValueError("Select an image to test")

        result = self.service.predict_image(
            model_path=self.test_model_edit.text().strip(),
            image_path=image_path,
            top_k=self.test_topk_spin.value(),
        )
        self._show_image_preview(image_path)
        return result

    def _predict_sample(self) -> dict[str, object]:
        result = self.service.predict_cifar10_sample(
            model_path=self.test_model_edit.text().strip(),
            data_root=self.data_dir_edit.text().strip(),
            sample_index=self.test_sample_spin.value(),
            top_k=self.test_topk_spin.value(),
        )
        self.test_image_edit.setText(result["preview_path"])
        self._show_image_preview(result["preview_path"])
        return result

    def _predict_batch(self) -> dict[str, object]:
        folder = Path(self.test_batch_edit.text().strip())
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f"Image folder does not exist: {folder}")

        image_paths = sorted(
            path for path in folder.iterdir()
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
        )
        if not image_paths:
            raise ValueError(f"No supported images found in: {folder}")

        results = self.service.predict_image_batch(
            model_path=self.test_model_edit.text().strip(),
            image_paths=image_paths,
            top_k=self.test_topk_spin.value(),
        )

        self._populate_batch_results(results)
        self._show_image_preview(image_paths[0])
        return {
            "folder": str(folder),
            "image_count": len(image_paths),
            "results": results,
        }

    def _populate_batch_results(self, results: list[dict[str, object]]) -> None:
        self.batch_results.setRowCount(len(results))

        for row, result in enumerate(results):
            image_path = str(result.get("image_path", ""))
            predicted = str(result.get("predicted_class", result.get("status", "")))
            confidence = result.get("confidence")
            status = str(result.get("status", "ok"))
            top_k = result.get("top_k", [])

            self.batch_results.setItem(row, 0, QTableWidgetItem(Path(image_path).name))
            self.batch_results.setItem(row, 1, QTableWidgetItem(predicted))
            self.batch_results.setItem(row, 2, QTableWidgetItem(f"{confidence:.4f}" if isinstance(confidence, float) else "-"))
            self.batch_results.setItem(row, 3, QTableWidgetItem(status))
            self.batch_results.setItem(row, 4, QTableWidgetItem(json.dumps(top_k, default=str)))

        self.batch_results.resizeColumnsToContents()
